import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import EvedexPerpetualDerivative


class EvedexPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'EvedexPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
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
        # Mapping from WebSocket symbol (e.g., XRPUSD) to trading pair (e.g., XRP-USD)
        self._ws_symbol_to_trading_pair: Dict[str, str] = {}
        # Ping task for keeping Centrifugo connection alive
        self._ping_task: Optional[asyncio.Task] = None
        self._ws_assistant: Optional[WSAssistant] = None

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        instrument_info = await self._request_instrument_info(trading_pair)
        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(instrument_info.get("markPrice", 0))),
            mark_price=Decimal(str(instrument_info.get("markPrice", 0))),
            next_funding_utc_timestamp=int(time.time()) + 3600,  # Default to 1 hour from now
            rate=Decimal(str(instrument_info.get("fundingRate", 0))),
        )
        return funding_info

    async def _request_instrument_info(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves instrument information including funding rate and mark price
        """
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "instrument": ex_trading_pair,
            "fields": "metrics"
        }
        data = await self._connector._api_get(
            path_url=CONSTANTS.INSTRUMENTS_PATH_URL,
            params=params,
            limit_id=CONSTANTS.INSTRUMENTS_PATH_URL)
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return data

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        path_url = CONSTANTS.ORDER_BOOK_PATH_URL.format(instrument=ex_trading_pair)

        data = await self._connector._api_get(
            path_url=path_url,
            params={},
            limit_id=CONSTANTS.ORDER_BOOK_PATH_URL)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_response.update({"trading_pair": trading_pair})

        # Convert Evedex dict format to standard format
        bids = [
            [str(entry.get("price", 0)), str(entry.get("quantity", 0))]
            for entry in snapshot_response.get("bids", [])
        ]
        asks = [
            [str(entry.get("price", 0)), str(entry.get("quantity", 0))]
            for entry in snapshot_response.get("asks", [])
        ]

        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": snapshot_response.get("t", int(time.time() * 1000)),
            "bids": bids,
            "asks": asks
        }, timestamp=snapshot_timestamp)
        return snapshot_msg

    _message_id: int = 0

    def _next_message_id(self) -> int:
        """Generate the next message ID for Centrifugo protocol."""
        self._message_id += 1
        return self._message_id

    async def _ping_loop(self, websocket_assistant: WSAssistant):
        """
        Sends Centrifugo protocol ping messages to keep the connection alive.
        Centrifugo uses application-level pings, not just WebSocket pings.
        """
        try:
            while True:
                await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                # Centrifugo protocol ping - empty object indicates ping
                ping_payload = {"ping": {}}
                ping_request: WSJSONRequest = WSJSONRequest(payload=ping_payload)
                await websocket_assistant.send(ping_request)
                self.logger().debug("Sent Centrifugo ping (order book)")
        except asyncio.CancelledError:
            self.logger().debug("Order book ping loop cancelled")
            raise
        except Exception as e:
            self.logger().warning(f"Order book ping loop error: {e}")

    async def _connected_websocket_assistant(self) -> WSAssistant:
        # Cancel any existing ping task
        if self._ping_task is not None and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        url = web_utils.wss_url(self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL + CONSTANTS.WS_PING_TIMEOUT)

        # Send Centrifugo connect message
        connect_payload = {
            "connect": {"name": "js"},
            "id": self._next_message_id()
        }
        connect_request: WSJSONRequest = WSJSONRequest(payload=connect_payload)
        await ws.send(connect_request)

        # Centrifugo server sends pings; respond with pong in message handler.
        self._ws_assistant = ws

        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        Centrifugo channel patterns (using : separator):
        - Heartbeat: futures-perp:heartbeat
        - Instruments: futures-perp:instruments
        - Order book: futures-perp:orderBook:{instrument}:OneTenth
        - Trades: futures-perp:trade:{instrument}

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            # Subscribe to heartbeat channel (no auth required)
            heartbeat_payload = {
                "subscribe": {
                    "channel": "futures-perp:heartbeat",
                    "flag": 1
                },
                "id": self._next_message_id()
            }
            subscribe_heartbeat_request: WSJSONRequest = WSJSONRequest(payload=heartbeat_payload)
            await ws.send(subscribe_heartbeat_request)

            # Subscribe to instruments channel
            instruments_payload = {
                "subscribe": {
                    "channel": "futures-perp:instruments",
                    "flag": 1
                },
                "id": self._next_message_id()
            }
            subscribe_instruments_request: WSJSONRequest = WSJSONRequest(payload=instruments_payload)
            await ws.send(subscribe_instruments_request)

            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                # WebSocket channels use symbol without hyphen (e.g., XRPUSD instead of XRP-USD)
                ws_symbol = symbol.replace("-", "")
                # Store mapping for parsing incoming messages
                self._ws_symbol_to_trading_pair[ws_symbol] = trading_pair

                # Subscribe to order book updates: futures-perp:orderBook-{instrument}-0.1
                orderbook_channel = f"futures-perp:orderBook-{ws_symbol}-0.1"
                orderbook_payload = {
                    "subscribe": {
                        "channel": orderbook_channel,
                        "flag": 1
                    },
                    "id": self._next_message_id()
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=orderbook_payload)
                await ws.send(subscribe_orderbook_request)

                # Subscribe to trade updates: futures-perp:recent-trade-{instrument}
                trade_channel = f"futures-perp:recent-trade-{ws_symbol}"
                trades_payload = {
                    "subscribe": {
                        "channel": trade_channel,
                        "flag": 1
                    },
                    "id": self._next_message_id()
                }
                subscribe_trades_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)
                await ws.send(subscribe_trades_request)

            # Subscribe to funding rate updates: futures-perp:fundingRate (global channel)
            funding_payload = {
                "subscribe": {
                    "channel": "futures-perp:position",
                    "flag": 1
                },
                "id": self._next_message_id()
            }
            subscribe_funding_request: WSJSONRequest = WSJSONRequest(payload=funding_payload)
            await ws.send(subscribe_funding_request)

            self.logger().info("Subscribed to public order book, trade and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading and delta streams...")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """Determine channel type from Centrifugo channel name.

        Centrifugo message format:
        - Push messages: {"push": {"channel": "...", "pub": {"data": {...}}}}
        - Direct: {"channel": "...", "data": {...}}
        """
        if not isinstance(event_message, dict):
            return ""
        channel = ""

        # Handle Centrifugo push message format
        if "push" in event_message:
            push_data = event_message.get("push", {})
            event_type = push_data.get("channel", "")

            # Centrifugo channels: futures-perp:orderBook:{instrument}:OneTenth, futures-perp:trade:{instrument}, futures-perp:fundingRate
            if "orderBook" in event_type or event_type.startswith("futures-perp:orderBook:"):
                channel = self._diff_messages_queue_key
            elif "recent-trade" in event_type or event_type.startswith("futures-perp:recent-trade:"):
                channel = self._trade_messages_queue_key
            elif "position" in event_type or event_type == "futures-perp:position":
                channel = self._funding_info_messages_queue_key
            return channel

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        # Centrifugo sends ping commands and expects pong replies.
        if event_message == {}:
            await websocket_assistant.send(WSJSONRequest(payload={}))
        elif "ping" in event_message:
            self.logger().debug("Received Centrifugo ping on perpetual order book stream; sending pong.")
            await websocket_assistant.send(WSJSONRequest(payload={"pong": {}}))

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """
        Subscribes to order book and trade channels for a single trading pair on an
        existing WebSocket connection.
        """
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot subscribe to {trading_pair}: WebSocket not connected")
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            ws_symbol = symbol.replace("-", "")
            self._ws_symbol_to_trading_pair[ws_symbol] = trading_pair

            orderbook_channel = f"futures-perp:orderBook-{ws_symbol}-0.1"
            orderbook_payload = {
                "subscribe": {
                    "channel": orderbook_channel,
                    "flag": 1
                },
                "id": self._next_message_id()
            }
            await self._ws_assistant.send(WSJSONRequest(payload=orderbook_payload))

            trade_channel = f"futures-perp:recent-trade-{ws_symbol}"
            trades_payload = {
                "subscribe": {
                    "channel": trade_channel,
                    "flag": 1
                },
                "id": self._next_message_id()
            }
            await self._ws_assistant.send(WSJSONRequest(payload=trades_payload))

            self.add_trading_pair(trading_pair)
            self.logger().info(f"Subscribed to {trading_pair} order book and trade channels")
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error subscribing to {trading_pair} channels")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """
        Unsubscribes from order book and trade channels for a single trading pair on an
        existing WebSocket connection.
        """
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot unsubscribe from {trading_pair}: WebSocket not connected")
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            ws_symbol = symbol.replace("-", "")

            orderbook_channel = f"futures-perp:orderBook-{ws_symbol}-0.1"
            trade_channel = f"futures-perp:recent-trade-{ws_symbol}"

            unsubscribe_payload = {
                "unsubscribe": {
                    "channel": orderbook_channel
                },
                "id": self._next_message_id()
            }
            await self._ws_assistant.send(WSJSONRequest(payload=unsubscribe_payload))

            unsubscribe_payload = {
                "unsubscribe": {
                    "channel": trade_channel
                },
                "id": self._next_message_id()
            }
            await self._ws_assistant.send(WSJSONRequest(payload=unsubscribe_payload))

            self._ws_symbol_to_trading_pair.pop(ws_symbol, None)
            self.remove_trading_pair(trading_pair)
            self.logger().info(f"Unsubscribed from {trading_pair} order book and trade channels")
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error unsubscribing from {trading_pair} channels")
            return False

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """Parse order book update from futures-perp:orderBook-{instrument}-0.1 channel.

        Centrifugo push format: {"push": {"channel": "...", "pub": {"data": {...}}}}
        Channel format: futures-perp:orderBook-XRPUSD-0.1
        """
        timestamp: float = time.time()

        # Handle Centrifugo push format
        if "push" in raw_message:
            push_data = raw_message.get("push", {})
            pub_data = push_data.get("pub", {})
            data = pub_data.get("data", {})
            instrument = data.get("instrument", "")

            try:
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(instrument)
            except KeyError:
                return
            orderbook = data.get("orderBook", {})

            # Handle Evedex dict format
            bids = [
                [str(entry.get("price", 0)), str(entry.get("quantity", 0))]
                for entry in orderbook.get("bids", [])
            ]
            asks = [
                [str(entry.get("price", 0)), str(entry.get("quantity", 0))]
                for entry in orderbook.get("asks", [])
            ]

            order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
                "trading_pair": trading_pair,
                "update_id": orderbook.get("t", int(time.time() * 1000)),
                "bids": bids,
                "asks": asks
            }, timestamp=timestamp)
            message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """Parse trade message from futures-perp:recent-trade-{instrument} channel.

        Centrifugo push format: {"push": {"channel": "...", "pub": {"data": {...}}}}
        Channel format: futures-perp:recent-trade-XRPUSD
        """
        # Handle Centrifugo push format
        if "push" in raw_message:
            push_data = raw_message.get("push", {})
            pub_data = push_data.get("pub", {})
            data = pub_data.get("data", {})

            trades = data if isinstance(data, list) else [data]
            for trade in trades:
                if not isinstance(trade, dict):
                    continue
                instrument = trade.get("instrument", "")
                try:
                    trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(instrument)
                except KeyError:
                    continue
                trade_message: OrderBookMessage = OrderBookMessage(
                    OrderBookMessageType.TRADE,
                    {
                        "trading_pair": trading_pair,
                        "trade_type": float(TradeType.SELL.value) if trade.get("side") == "SELL" else float(TradeType.BUY.value),
                        "trade_id": trade.get("executionId", str(int(time.time() * 1000))),
                        "update_id": trade.get("executionId", str(int(time.time() * 1000))),
                        "price": str(trade.get("fillPrice", 0)),
                        "amount": str(trade.get("fillQuantity", 0)),
                    },
                    timestamp=time.time()
                )
                message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse funding rate message from futures-perp:fundingRate channel.

        Centrifugo push format: {"push": {"channel": "...", "pub": {"data": {...}}}}

        FundingRateEvent structure:
        {
            instrument: string,
            fundingRate: string,
            createdAt: number
        }
        """
        # Handle Centrifugo push format
        if "push" in raw_message:
            push_data = raw_message.get("push", {})
            pub_data = push_data.get("pub", {})
            data = pub_data.get("data", {})

            instrument = data.get("instrument", "")

            try:
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(instrument)
            except KeyError:
                return

            funding_info_update = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(str(data.get("markPrice", 0))),
                mark_price=Decimal(str(data.get("markPrice", 0))),
                next_funding_utc_timestamp=int(data.get("createdAt", time.time() * 1000)) // 1000 + 3600,
                rate=Decimal(str(data.get("fundingRate", 0))),
            )
            message_queue.put_nowait(funding_info_update)

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        """
        Called when the order book stream gets interrupted.
        Cleans up the ping task and connection state.
        """
        # Cancel the ping task
        if self._ping_task is not None and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        self._ws_assistant = None
        await super()._on_order_stream_interruption(websocket_assistant=websocket_assistant)
