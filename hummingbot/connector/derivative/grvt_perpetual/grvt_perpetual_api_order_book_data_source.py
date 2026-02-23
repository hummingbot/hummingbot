import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GRVTPerpetualDerivative


class GRVTPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "GRVTPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        params = {"instrument": await self._connector.exchange_symbol_associated_to_pair(trading_pair)}
        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.public_rest_url(CONSTANTS.ORDERBOOK_URL, self._domain)
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=params,
            throttler_limit_id=CONSTANTS.ORDERBOOK_URL,
        )
        return response

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_data = snapshot.get("result", {})
        snapshot_timestamp: float = float(snapshot_data.get("time", 0)) * 1e-9
        update_id: int = int(snapshot_data.get("seq", 0))

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid["price"], bid["size"]) for bid in snapshot_data.get("bids", [])],
            "asks": [(ask["price"], ask["size"]) for ask in snapshot_data.get("asks", [])],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp,
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws_url = CONSTANTS.PROD_MARKET_WS_URL if self._domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_MARKET_WS_URL
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                payload = {
                    "type": "subscribe",
                    "channel": "book",
                    "instrument": symbol
                }
                subscribe_request = WSJSONRequest(payload)
                await ws.send(subscribe_request)

                payload = {
                    "type": "subscribe",
                    "channel": "trade",
                    "instrument": symbol
                }
                subscribe_request = WSJSONRequest(payload)
                await ws.send(subscribe_request)
            self.logger().info("Subscribed to public order book and trade channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book trading and delta streams.", exc_info=True)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = event_message.get("channel", "")
        if channel == "book":
            return self._diff_messages_queue_key
        elif channel == "trade":
            return self._trade_messages_queue_key
        return ""

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "data" not in raw_message:
            return
        data = raw_message["data"]
        symbol = data.get("instrument")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        
        timestamp = float(data.get("time", 0)) * 1e-9
        update_id = int(data.get("seq", 0))

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid["price"], bid["size"]) for bid in data.get("bids", [])],
            "asks": [(ask["price"], ask["size"]) for ask in data.get("asks", [])],
        }
        diff_message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.DIFF,
            order_book_message_content,
            timestamp,
        )
        message_queue.put_nowait(diff_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "data" not in raw_message:
            return
        data = raw_message["data"]
        for trade in data:
            symbol = trade.get("instrument")
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
            
            timestamp = float(trade.get("time", 0)) * 1e-9
            trade_message_content = {
                "trade_id": trade.get("id"),
                "trading_pair": trading_pair,
                "trade_type": float(1) if trade.get("taker_side") == "buy" else float(2),
                "amount": float(trade.get("size")),
                "price": float(trade.get("price")),
            }
            trade_message: OrderBookMessage = OrderBookMessage(
                OrderBookMessageType.TRADE,
                trade_message_content,
                timestamp,
            )
            message_queue.put_nowait(trade_message)
