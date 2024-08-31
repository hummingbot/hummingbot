import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.exchange.hyperliquid.hyperliquid_constants as CONSTANTS
import hummingbot.connector.exchange.hyperliquid.hyperliquid_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.hyperliquid.hyperliquid_exchange import HyperliquidExchange


class HyperliquidAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'HyperliquidExchange',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        coin = ex_trading_pair.split("-")[0]
        params = {
            "type": 'l2Book',
            "coin": coin
        }

        data = await self._connector._api_post(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            data=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_response.update({"trading_pair": trading_pair})
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": snapshot_response["trading_pair"],
            "update_id": int(snapshot_response['time']),
            "bids": [[float(i['px']), float(i['sz'])] for i in snapshot_response['levels'][0]],
            "asks": [[float(i['px']), float(i['sz'])] for i in snapshot_response['levels'][1]],
        }, timestamp=int(snapshot_response['time']))
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                coin = ex_trading_pair.split("-")[0]
                trades_payload = {
                    "method": "subscribe",
                    "subscription": {
                        "type": CONSTANTS.TRADES_ENDPOINT_NAME,
                        "coin": ex_trading_pair,
                    }
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

                order_book_payload = {
                    "method": "subscribe",
                    "subscription": {
                        "type": CONSTANTS.DEPTH_ENDPOINT_NAME,
                        "coin": coin,
                    }
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

                await ws.send(subscribe_trade_request)
                await ws.send(subscribe_orderbook_request)

                self.logger().info("Subscribed to public order book, trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            stream_name = event_message.get("channel")
            if "l2Book" in stream_name:
                channel = self._snapshot_messages_queue_key
            elif "trades" in stream_name:
                channel = self._trade_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = raw_message["data"]["time"] * 1e-3
        trading_pair = raw_message["data"]["coin"]
        data = raw_message["data"]
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "update_id": data["time"],
            "bids": [[float(i['px']), float(i['sz'])] for i in data["levels"][0]],
            "asks": [[float(i['px']), float(i['sz'])] for i in data["levels"][1]],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = raw_message["data"]["time"] * 1e-3
        trading_pair = raw_message["data"]["coin"]
        data = raw_message["data"]
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": data["time"],
            "bids": [[float(i['px']), float(i['sz'])] for i in data["levels"][0]],
            "asks": [[float(i['px']), float(i['sz'])] for i in data["levels"][1]],
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message["data"]
        for trade_data in data:
            trading_pair = trade_data["coin"]
            trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade_data["side"] == "A" else float(
                    TradeType.BUY.value),
                "trade_id": trade_data["hash"],
                "price": float(trade_data["px"]),
                "amount": float(trade_data["sz"])
            }, timestamp=trade_data["time"] * 1e-3)

            message_queue.put_nowait(trade_message)