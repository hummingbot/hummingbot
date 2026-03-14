import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import (
        GRVTPerpetualDerivative,
    )


class GRVTPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _gpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()
    _DYNAMIC_SUBSCRIBE_ID_START = 100
    _next_subscribe_id: int = _DYNAMIC_SUBSCRIBE_ID_START

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'GRVTPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._trade_messages_queue_key = CONSTANTS.TRADE_STREAM_ID
        self._diff_messages_queue_key = CONSTANTS.DIFF_STREAM_ID
        self._funding_info_messages_queue_key = CONSTANTS.FUNDING_INFO_STREAM_ID
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol_info: Dict[str, Any] = await self._request_complete_funding_info(trading_pair)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(symbol_info.get("indexPrice", "0")),
            mark_price=Decimal(symbol_info.get("markPrice", "0")),
            next_funding_utc_timestamp=int(float(symbol_info.get("nextFundingTime", "0")) * 1e-3),
            rate=Decimal(symbol_info.get("lastFundingRate", "0")),
        )
        return funding_info

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        params = {
            "symbol": ex_trading_pair,
            "limit": 1000
        }

        data = await self._connector._api_get(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            params=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_response.update({"trading_pair": trading_pair})
        
        # GRVT format: bids and asks are arrays of [price, quantity]
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": snapshot_response["trading_pair"],
            "update_id": snapshot_response.get("lastUpdateId", snapshot_response.get("u", 0)),
            "bids": [[bid[0], bid[1]] for bid in snapshot_response.get("bids", [])],
            "asks": [[ask[0], ask[1]] for ask in snapshot_response.get("asks", [])]
        }, timestamp=snapshot_timestamp)
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            stream_id_channel_pairs = [
                (CONSTANTS.DIFF_STREAM_ID, "depth"),
                (CONSTANTS.TRADE_STREAM_ID, "trade"),
                (CONSTANTS.FUNDING_INFO_STREAM_ID, "mark_price"),
            ]
            for stream_id, channel in stream_id_channel_pairs:
                params = []
                for trading_pair in self._trading_pairs:
                    symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                    params.append(f"{symbol.lower()}:{channel}")
                payload = {
                    "method": "SUBSCRIBE",
                    "params": params,
                    "id": stream_id,
                }
                subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                await ws.send(subscribe_request)
            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            stream_name = event_message.get("stream", "")
            if "depth" in stream_name:
                channel = self._diff_messages_queue_key
            elif "trade" in stream_name:
                channel = self._trade_messages_queue_key
            elif "mark_price" in stream_name:
                channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = time.time()
        data = raw_message.get("data", raw_message)
        
        # Convert exchange symbol to trading pair
        if "s" in data:
            data["s"] = await self._connector.trading_pair_associated_to_exchange_symbol(data["s"])
        
        order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": data.get("s", raw_message.get("trading_pair", "")),
            "update_id": data.get("u", data.get("lastUpdateId", 0)),
            "bids": [[bid[0], bid[1]] for bid in data.get("b", data.get("bids", []))],
            "asks": [[ask[0], ask[1]] for ask in data.get("a", data.get("asks", []))]
        }, timestamp=timestamp)
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", raw_message)
        
        # Convert exchange symbol to trading pair
        if "s" in data:
            data["s"] = await self._connector.trading_pair_associated_to_exchange_symbol(data["s"])
        
        # GRVT trade message format
        trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": data.get("s", ""),
            "trade_type": float(TradeType.SELL.value) if data.get("m", False) else float(TradeType.BUY.value),
            "trade_id": data.get("t", data.get("tradeId", 0)),
            "update_id": data.get("E", data.get("eventTime", 0)),
            "price": data.get("p", "0"),
            "amount": data.get("q", data.get("quantity", "0"))
        }, timestamp=(data.get("E", data.get("eventTime", 0))) * 1e-3)

        message_queue.put_nowait(trade_message)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot_msg: OrderBookMessage = await self._order_book_snapshot(trading_pair)
                    output.put_nowait(snapshot_msg)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                delta = CONSTANTS.ONE_HOUR - time.time() % CONSTANTS.ONE_HOUR
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds...", exc_info=True
                )
                await self._sleep(5.0)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):

        data: Dict[str, Any] = raw_message.get("data", raw_message)
        
        trading_pair = data.get("s", "")
        if trading_pair:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(trading_pair)

        if trading_pair not in self._trading_pairs:
            return
        
        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(data.get("i", data.get("indexPrice", "0"))),
            mark_price=Decimal(data.get("p", data.get("markPrice", "0"))),
            next_funding_utc_timestamp=int(float(data.get("T", data.get("nextFundingTime", "0"))) * 1e-3),
            rate=Decimal(data.get("r", data.get("lastFundingRate", "0"))),
        )

        message_queue.put_nowait(funding_info)

    async def _request_complete_funding_info(self, trading_pair: str):
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = await self._connector._api_get(
            path_url=CONSTANTS.MARK_PRICE_URL,
            params={"symbol": ex_trading_pair},
            is_auth_required=True)
        return data

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """
        Subscribes to order book, trade, and funding info channels for a single trading pair
        on the existing WebSocket connection.

        :param trading_pair: the trading pair to subscribe to
        :return: True if subscription was successful, False otherwise
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot subscribe to {trading_pair}: WebSocket not connected"
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            stream_id_channel_pairs = [
                (self._get_next_subscribe_id(), "depth"),
                (self._get_next_subscribe_id(), "trade"),
                (self._get_next_subscribe_id(), "mark_price"),
            ]

            for stream_id, channel in stream_id_channel_pairs:
                payload = {
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol.lower()}:{channel}"],
                    "id": stream_id,
                }
                subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                await self._ws_assistant.send(subscribe_request)

            self.add_trading_pair(trading_pair)
            self.logger().info(f"Subscribed to {trading_pair} order book, trade and funding info channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error subscribing to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """
        Unsubscribes from order book, trade, and funding info channels for a single trading pair
        on the existing WebSocket connection.

        :param trading_pair: the trading pair to unsubscribe from
        :return: True if unsubscription was successful, False otherwise
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected"
            )
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            unsubscribe_params = [
                f"{symbol.lower()}:depth",
                f"{symbol.lower()}:trade",
                f"{symbol.lower()}:mark_price",
            ]

            payload = {
                "method": "UNSUBSCRIBE",
                "params": unsubscribe_params,
                "id": self._get_next_subscribe_id(),
            }
            unsubscribe_request: WSJSONRequest = WSJSONRequest(payload)
            await self._ws_assistant.send(unsubscribe_request)

            self.remove_trading_pair(trading_pair)
            self.logger().info(f"Unsubscribed from {trading_pair} order book, trade and funding info channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error unsubscribing from {trading_pair}")
            return False

    @classmethod
    def _get_next_subscribe_id(cls) -> int:
        """Returns the next subscription ID and increments the counter."""
        current_id = cls._next_subscribe_id
        cls._next_subscribe_id += 1
        return current_id
