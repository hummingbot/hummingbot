import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
        DecibelPerpetualDerivative,
    )


class DecibelPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'DecibelPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._funding_info_messages_queue_key = "funding_info"
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(
            self,
            trading_pairs: List[str],
            domain: Optional[str] = None,
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair
        )
        market_address = self._connector.market_name_to_address.get(ex_trading_pair, ex_trading_pair)

        try:
            prices_data = await self._connector._api_get(
                path_url=CONSTANTS.PRICES_URL,
                params={},
            )
            # prices_data is a list of market price objects
            for price_info in prices_data:
                if price_info.get("market") == market_address or price_info.get("symbol") == ex_trading_pair:
                    return FundingInfo(
                        trading_pair=trading_pair,
                        index_price=Decimal(str(price_info.get("oracle_price", "0"))),
                        mark_price=Decimal(str(price_info.get("mark_price", "0"))),
                        next_funding_utc_timestamp=self._next_funding_time(),
                        rate=Decimal(str(price_info.get("funding_rate", "0"))),
                    )
        except Exception:
            self.logger().exception(f"Error fetching funding info for {trading_pair}")

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal("0"),
            mark_price=Decimal("0"),
            next_funding_utc_timestamp=self._next_funding_time(),
            rate=Decimal("0"),
        )

    async def listen_for_funding_info(self, output: asyncio.Queue):
        message_queue = self._message_queue[self._funding_info_messages_queue_key]
        while True:
            try:
                funding_info_event = await message_queue.get()
                await self._parse_funding_info_message(funding_info_event, output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error when processing public funding info updates from exchange"
                )
                await self._sleep(5)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair
        )
        market_address = self._connector.market_name_to_address.get(ex_trading_pair, ex_trading_pair)

        data = await self._connector._api_get(
            path_url=CONSTANTS.DEPTH_URL,
            params={"market": market_address},
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp = int(time.time() * 1e3)

        snapshot_msg = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": snapshot_timestamp,
                "bids": [
                    [float(bid["price"]), float(bid["size"])]
                    for bid in snapshot_response.get("bids", [])
                ],
                "asks": [
                    [float(ask["price"]), float(ask["size"])]
                    for ask in snapshot_response.get("asks", [])
                ],
            },
            timestamp=snapshot_timestamp,
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.wss_url(self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        # Decibel uses Sec-Websocket-Protocol for auth
        protocols = []
        if self._connector._auth is not None:
            protocols = self._connector._auth.get_ws_protocols()
        await ws.connect(
            ws_url=url,
            ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL,
            ws_headers={"Sec-Websocket-Protocol": ", ".join(protocols)} if protocols else {},
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                market_address = self._connector.market_name_to_address.get(ex_symbol, ex_symbol)

                # Subscribe to depth
                depth_payload = {
                    "method": "subscribe",
                    "topic": f"{CONSTANTS.WS_DEPTH_TOPIC}:{market_address}",
                }
                await ws.send(WSJSONRequest(payload=depth_payload))

                # Subscribe to trades
                trades_payload = {
                    "method": "subscribe",
                    "topic": f"{CONSTANTS.WS_TRADES_TOPIC}:{market_address}",
                }
                await ws.send(WSJSONRequest(payload=trades_payload))

                # Subscribe to prices for funding info
                prices_payload = {
                    "method": "subscribe",
                    "topic": f"{CONSTANTS.WS_PRICES_TOPIC}:{market_address}",
                }
                await ws.send(WSJSONRequest(payload=prices_payload))

            self.logger().info("Subscribed to public order book, trade, and funding info channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book data streams."
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            topic = event_message.get("topic", "")
            if topic.startswith(CONSTANTS.WS_DEPTH_TOPIC):
                channel = self._snapshot_messages_queue_key
            elif topic.startswith(CONSTANTS.WS_TRADES_TOPIC):
                channel = self._trade_messages_queue_key
            elif topic.startswith(CONSTANTS.WS_PRICES_TOPIC):
                channel = self._funding_info_messages_queue_key
        return channel

    async def _parse_order_book_diff_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        await self._parse_order_book_snapshot_message(raw_message, message_queue)

    async def _parse_order_book_snapshot_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        data = raw_message.get("data", {})
        topic = raw_message.get("topic", "")
        # Extract market address from topic: "depth:0x..."
        market_address = topic.split(":", 1)[-1] if ":" in topic else ""

        # Resolve trading pair
        trading_pair = None
        for name, addr in self._connector.market_name_to_address.items():
            if addr == market_address:
                try:
                    trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(name)
                except KeyError:
                    continue
                break

        if trading_pair is None:
            return

        timestamp = int(time.time() * 1e3)
        order_book_message = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": timestamp,
                "bids": [
                    [float(bid["price"]), float(bid["size"])]
                    for bid in data.get("bids", [])
                ],
                "asks": [
                    [float(ask["price"]), float(ask["size"])]
                    for ask in data.get("asks", [])
                ],
            },
            timestamp=timestamp,
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        data = raw_message.get("data", {})
        topic = raw_message.get("topic", "")
        market_address = topic.split(":", 1)[-1] if ":" in topic else ""

        trading_pair = None
        for name, addr in self._connector.market_name_to_address.items():
            if addr == market_address:
                try:
                    trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(name)
                except KeyError:
                    continue
                break

        if trading_pair is None:
            return

        trades = data if isinstance(data, list) else [data]
        for trade_data in trades:
            trade_timestamp = trade_data.get("timestamp", time.time())
            trade_message = OrderBookMessage(
                OrderBookMessageType.TRADE,
                {
                    "trading_pair": trading_pair,
                    "trade_type": float(TradeType.BUY.value)
                    if trade_data.get("side", "").lower() == "buy"
                    else float(TradeType.SELL.value),
                    "trade_id": str(trade_data.get("trade_id", trade_data.get("id", ""))),
                    "price": float(trade_data.get("price", 0)),
                    "amount": float(trade_data.get("size", trade_data.get("quantity", 0))),
                },
                timestamp=trade_timestamp,
            )
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        try:
            data = raw_message.get("data", {})
            topic = raw_message.get("topic", "")
            market_address = topic.split(":", 1)[-1] if ":" in topic else ""

            trading_pair = None
            for name, addr in self._connector.market_name_to_address.items():
                if addr == market_address:
                    try:
                        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(name)
                    except KeyError:
                        continue
                    break

            if trading_pair is None or trading_pair not in self._trading_pairs:
                return

            funding_info = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(str(data.get("oracle_price", "0"))),
                mark_price=Decimal(str(data.get("mark_price", "0"))),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal(str(data.get("funding_rate", "0"))),
            )
            message_queue.put_nowait(funding_info)
        except Exception as e:
            self.logger().debug(f"Error parsing funding info message: {e}")

    def _next_funding_time(self) -> int:
        """Funding settlement occurs every 1 hour."""
        return int(((time.time() // 3600) + 1) * 3600)
