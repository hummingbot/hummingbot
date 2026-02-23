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
        GrvtPerpetualDerivative,
    )


class GrvtPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    """
    Data source for GRVT perpetual order book, trades, and funding info.

    Uses REST (POST) for snapshots and WebSocket for streaming updates.
    All GRVT REST endpoints use POST method.
    """

    _bpobds_logger: Optional[HummingbotLogger] = None
    _trading_pair_symbol_map: Dict[str, Mapping[str, str]] = {}
    _mapping_initialization_lock = asyncio.Lock()

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "GrvtPerpetualDerivative",
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
        """
        Fetches funding info for a trading pair via the GRVT REST API.

        GRVT endpoint: POST /full/v1/funding
        """
        instrument = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair
        )

        try:
            response = await self._connector._api_post(
                path_url=CONSTANTS.FUNDING_RATE_URL,
                data={"instrument": instrument},
            )

            result = response.get("result", response)
            # Handle both list and dict responses
            if isinstance(result, list) and len(result) > 0:
                funding_data = result[0]
            elif isinstance(result, dict):
                funding_data = result
            else:
                funding_data = {}

            return FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal(str(funding_data.get("index_price", "0"))),
                mark_price=Decimal(str(funding_data.get("mark_price", "0"))),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal(str(funding_data.get("funding_rate", "0"))),
            )
        except Exception:
            self.logger().exception(
                f"Error fetching funding info for {trading_pair}"
            )
            return FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal("0"),
                mark_price=Decimal("0"),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal("0"),
            )

    async def listen_for_funding_info(self, output: asyncio.Queue):
        """
        Reads funding info events from WebSocket queue and publishes updates.
        """
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

    async def _request_order_book_snapshot(
        self, trading_pair: str
    ) -> Dict[str, Any]:
        """
        Fetches a full order book snapshot via REST.

        GRVT endpoint: POST /full/v1/book
        """
        instrument = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair
        )
        params = {
            "instrument": instrument,
            "depth": 20,
        }
        data = await self._connector._api_post(
            path_url=CONSTANTS.ORDERBOOK_URL,
            data=params,
        )
        return data

    async def _order_book_snapshot(
        self, trading_pair: str
    ) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(
            trading_pair
        )
        result = snapshot_response.get("result", snapshot_response)
        timestamp = int(time.time() * 1e3)

        # GRVT book format: {"bids": [{"price": "...", "size": "..."}], "asks": [...]}
        bids = result.get("bids", [])
        asks = result.get("asks", [])

        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": timestamp,
                "bids": [
                    [float(b.get("price", b.get("px", 0))),
                     float(b.get("size", b.get("sz", 0)))]
                    for b in bids
                ],
                "asks": [
                    [float(a.get("price", a.get("px", 0))),
                     float(a.get("size", a.get("sz", 0)))]
                    for a in asks
                ],
            },
            timestamp=timestamp,
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.market_data_wss_url(self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=url,
            ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL,
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to order book, trade, and funding info channels for all
        configured trading pairs.

        GRVT WS subscription format:
        {"channel": "book.s", "instrument": "BTC_USDT_Perp"}
        """
        try:
            for trading_pair in self._trading_pairs:
                instrument = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair
                )

                # Subscribe to trades
                trades_payload = {
                    "method": "subscribe",
                    "params": {
                        "channel": CONSTANTS.WS_TRADES_CHANNEL,
                        "instrument": instrument,
                    },
                }
                subscribe_trade_request = WSJSONRequest(payload=trades_payload)

                # Subscribe to order book
                order_book_payload = {
                    "method": "subscribe",
                    "params": {
                        "channel": CONSTANTS.WS_BOOK_CHANNEL,
                        "instrument": instrument,
                    },
                }
                subscribe_orderbook_request = WSJSONRequest(
                    payload=order_book_payload
                )

                # Subscribe to ticker (for funding info)
                funding_info_payload = {
                    "method": "subscribe",
                    "params": {
                        "channel": CONSTANTS.WS_TICKER_CHANNEL,
                        "instrument": instrument,
                    },
                }
                subscribe_funding_info_request = WSJSONRequest(
                    payload=funding_info_payload
                )

                await ws.send(subscribe_trade_request)
                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_funding_info_request)

                self.logger().info(
                    f"Subscribed to public order book, trade, and ticker channels "
                    f"for {instrument}..."
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book data streams."
            )
            raise

    def _channel_originating_message(
        self, event_message: Dict[str, Any]
    ) -> str:
        channel = ""
        if "error" not in event_message:
            stream_name = event_message.get("channel", "")
            if "book" in stream_name:
                channel = self._snapshot_messages_queue_key
            elif "trade" in stream_name:
                channel = self._trade_messages_queue_key
            elif "ticker" in stream_name:
                channel = self._funding_info_messages_queue_key
        return channel

    def _parse_instrument_from_message(
        self, raw_message: Dict[str, Any]
    ) -> str:
        """Extracts the instrument identifier from a WS message."""
        data = raw_message.get("data", {})
        if isinstance(data, dict):
            return data.get("instrument", "")
        elif isinstance(data, list) and len(data) > 0:
            return data[0].get("instrument", "")
        return ""

    async def _parse_order_book_diff_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        instrument = self._parse_instrument_from_message(raw_message)
        data = raw_message.get("data", {})
        timestamp = float(data.get("timestamp", time.time() * 1e3))

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            instrument
        )

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        order_book_message = OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": trading_pair,
                "update_id": int(timestamp),
                "bids": [
                    [float(b.get("price", b.get("px", 0))),
                     float(b.get("size", b.get("sz", 0)))]
                    for b in bids
                ],
                "asks": [
                    [float(a.get("price", a.get("px", 0))),
                     float(a.get("size", a.get("sz", 0)))]
                    for a in asks
                ],
            },
            timestamp=timestamp * 1e-3,
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        instrument = self._parse_instrument_from_message(raw_message)
        data = raw_message.get("data", {})
        timestamp = float(data.get("timestamp", time.time() * 1e3))

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            instrument
        )

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        order_book_message = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(timestamp),
                "bids": [
                    [float(b.get("price", b.get("px", 0))),
                     float(b.get("size", b.get("sz", 0)))]
                    for b in bids
                ],
                "asks": [
                    [float(a.get("price", a.get("px", 0))),
                     float(a.get("size", a.get("sz", 0)))]
                    for a in asks
                ],
            },
            timestamp=timestamp * 1e-3,
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        instrument = self._parse_instrument_from_message(raw_message)
        data = raw_message.get("data", {})

        # GRVT trade data can be a list of trades or a single trade
        trades = data if isinstance(data, list) else [data]

        for trade_data in trades:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                instrument
            )

            # GRVT uses "is_buyer_maker" or "side" for trade direction
            side = trade_data.get("side", "")
            if side.upper() == "SELL" or trade_data.get("is_buyer_maker", False):
                trade_type = float(TradeType.SELL.value)
            else:
                trade_type = float(TradeType.BUY.value)

            trade_id = trade_data.get("trade_id", trade_data.get("id", ""))
            price = float(trade_data.get("price", trade_data.get("px", 0)))
            size = float(trade_data.get("size", trade_data.get("sz", 0)))
            ts = trade_data.get("timestamp", trade_data.get("time", time.time() * 1e3))

            trade_message = OrderBookMessage(
                OrderBookMessageType.TRADE,
                {
                    "trading_pair": trading_pair,
                    "trade_type": trade_type,
                    "trade_id": str(trade_id),
                    "price": price,
                    "amount": size,
                },
                timestamp=float(ts) * 1e-3,
            )
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        try:
            data = raw_message.get("data", {})
            instrument = data.get("instrument", "")

            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                instrument
            )

            if trading_pair not in self._trading_pairs:
                return

            funding_info = FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(str(data.get("index_price", "0"))),
                mark_price=Decimal(str(data.get("mark_price", "0"))),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal(str(data.get("funding_rate", "0"))),
            )
            message_queue.put_nowait(funding_info)
        except Exception as e:
            self.logger().debug(f"Error parsing funding info message: {e}")

    def _next_funding_time(self) -> int:
        """
        GRVT funding settlement occurs every 8 hours.
        Returns the next funding timestamp.
        """
        interval = 8 * 3600  # 8 hours
        return int(((time.time() // interval) + 1) * interval)

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """
        Subscribe to order book channels for a single trading pair dynamically.
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot subscribe to {trading_pair}: WebSocket connection not established."
            )
            return False

        try:
            instrument = await self._connector.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair
            )

            trades_payload = {
                "method": "subscribe",
                "params": {
                    "channel": CONSTANTS.WS_TRADES_CHANNEL,
                    "instrument": instrument,
                },
            }
            subscribe_trade_request = WSJSONRequest(payload=trades_payload)

            order_book_payload = {
                "method": "subscribe",
                "params": {
                    "channel": CONSTANTS.WS_BOOK_CHANNEL,
                    "instrument": instrument,
                },
            }
            subscribe_orderbook_request = WSJSONRequest(
                payload=order_book_payload
            )

            await self._ws_assistant.send(subscribe_trade_request)
            await self._ws_assistant.send(subscribe_orderbook_request)

            self.add_trading_pair(trading_pair)
            self.logger().info(f"Successfully subscribed to {trading_pair}")
            return True

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error subscribing to {trading_pair}: {e}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """
        Unsubscribe from order book channels for a single trading pair.
        """
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected."
            )
            return False

        try:
            instrument = await self._connector.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair
            )

            trades_payload = {
                "method": "unsubscribe",
                "params": {
                    "channel": CONSTANTS.WS_TRADES_CHANNEL,
                    "instrument": instrument,
                },
            }
            unsubscribe_trade_request = WSJSONRequest(payload=trades_payload)

            order_book_payload = {
                "method": "unsubscribe",
                "params": {
                    "channel": CONSTANTS.WS_BOOK_CHANNEL,
                    "instrument": instrument,
                },
            }
            unsubscribe_orderbook_request = WSJSONRequest(
                payload=order_book_payload
            )

            await self._ws_assistant.send(unsubscribe_trade_request)
            await self._ws_assistant.send(unsubscribe_orderbook_request)

            self.remove_trading_pair(trading_pair)
            self.logger().info(
                f"Successfully unsubscribed from {trading_pair}"
            )
            return True

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(
                f"Error unsubscribing from {trading_pair}: {e}"
            )
            return False
