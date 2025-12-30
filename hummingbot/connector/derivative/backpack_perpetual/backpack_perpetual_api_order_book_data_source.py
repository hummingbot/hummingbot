import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.backpack_perpetual import (
    backpack_perpetual_constants as CONSTANTS,
    backpack_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
        BackpackPerpetualDerivative,
    )


class BackpackPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    """
    Order book data source for Backpack Perpetual.

    Handles:
    - REST order book snapshots
    - WebSocket order book diff updates
    - WebSocket trade events
    """

    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "BackpackPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair
        )

        params = {
            "symbol": ex_trading_pair,
            "limit": 1000,
        }

        data = await self._connector._api_get(
            path_url=CONSTANTS.DEPTH_URL,
            params=params,
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        import time

        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()

        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(snapshot.get("lastUpdateId", snapshot_timestamp * 1000)),
                "bids": self._parse_orders(snapshot.get("bids", [])),
                "asks": self._parse_orders(snapshot.get("asks", [])),
            },
            timestamp=snapshot_timestamp,
        )
        return snapshot_msg

    def _parse_orders(self, orders: List) -> List[List[float]]:
        result = []
        for order in orders:
            if isinstance(order, (list, tuple)) and len(order) >= 2:
                price = float(order[0])
                quantity = float(order[1])
                result.append([price, quantity])
        return result

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.wss_url(self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            streams = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair
                )
                streams.append(f"{CONSTANTS.WS_DEPTH_CHANNEL}.{symbol}")
                streams.append(f"{CONSTANTS.WS_TRADE_CHANNEL}.{symbol}")

            subscribe_payload = {
                "method": "SUBSCRIBE",
                "params": streams,
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=subscribe_payload)
            await ws.send(subscribe_request)

            self.logger().info(
                f"Subscribed to public order book and trade channels for {len(self._trading_pairs)} pairs"
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book data streams.",
                exc_info=True,
            )
            raise

    async def _parse_order_book_diff_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        data = raw_message.get("data", raw_message)
        stream = raw_message.get("stream", "")

        symbol = stream.split(".")[-1] if "." in stream else data.get("s", "")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        timestamp: float = float(data.get("T", 0)) / 1e6 if "T" in data else None
        if timestamp is None:
            import time
            timestamp = time.time()

        order_book_message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": trading_pair,
                "update_id": int(data.get("u", timestamp * 1000)),
                "bids": self._parse_orders(data.get("b", data.get("bids", []))),
                "asks": self._parse_orders(data.get("a", data.get("asks", []))),
            },
            timestamp=timestamp,
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        data = raw_message.get("data", raw_message)
        stream = raw_message.get("stream", "")

        symbol = stream.split(".")[-1] if "." in stream else data.get("s", "")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        trades = data if isinstance(data, list) else [data]

        for trade_data in trades:
            timestamp = float(trade_data.get("T", 0)) / 1e6 if "T" in trade_data else None
            if timestamp is None:
                import time
                timestamp = time.time()

            trade_message: OrderBookMessage = OrderBookMessage(
                OrderBookMessageType.TRADE,
                {
                    "trading_pair": trading_pair,
                    "trade_type": 1.0 if trade_data.get("m", False) else 2.0,
                    "trade_id": str(trade_data.get("t", trade_data.get("id", timestamp))),
                    "price": float(trade_data.get("p", trade_data.get("price", 0))),
                    "amount": float(trade_data.get("q", trade_data.get("quantity", 0))),
                },
                timestamp=timestamp,
            )
            message_queue.put_nowait(trade_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        stream = event_message.get("stream", "")

        if stream:
            if stream.startswith(CONSTANTS.WS_DEPTH_CHANNEL):
                channel = self._diff_messages_queue_key
            elif stream.startswith(CONSTANTS.WS_TRADE_CHANNEL):
                channel = self._trade_messages_queue_key

        return channel

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Get the current funding information for a trading pair.

        Args:
            trading_pair: The trading pair in Hummingbot format (e.g., "BTC-USDC")

        Returns:
            FundingInfo with current funding rate, mark price, index price, and next funding time
        """
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair
        )

        # Get funding rate
        funding_data = await self._connector._api_get(
            path_url=CONSTANTS.FUNDING_RATES_URL,
            params={"symbol": ex_trading_pair},
        )

        # Get mark price for index/mark prices
        mark_price_data = await self._connector._api_get(
            path_url=CONSTANTS.MARK_PRICES_URL,
        )

        # Parse funding rate - response is a list
        funding_rate = Decimal("0")
        if isinstance(funding_data, list) and len(funding_data) > 0:
            for item in funding_data:
                if item.get("symbol") == ex_trading_pair:
                    funding_rate = Decimal(str(item.get("fundingRate", "0")))
                    break

        # Parse mark price and index price
        mark_price = Decimal("0")
        index_price = Decimal("0")
        if isinstance(mark_price_data, list):
            for item in mark_price_data:
                if item.get("symbol") == ex_trading_pair:
                    mark_price = Decimal(str(item.get("markPrice", "0")))
                    index_price = Decimal(str(item.get("indexPrice", mark_price_data.get("markPrice", "0"))))
                    break

        # Calculate next funding time (Backpack settles funding every 8 hours)
        next_funding_utc_timestamp = self._next_funding_time()

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=index_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=next_funding_utc_timestamp,
            rate=funding_rate,
        )

    async def listen_for_funding_info(self, output: asyncio.Queue):
        """
        Poll for funding info updates since Backpack doesn't have a dedicated funding WS channel.
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    funding_info = await self.get_funding_info(trading_pair)
                    funding_info_update = FundingInfoUpdate(
                        trading_pair=trading_pair,
                        index_price=funding_info.index_price,
                        mark_price=funding_info.mark_price,
                        next_funding_utc_timestamp=funding_info.next_funding_utc_timestamp,
                        rate=funding_info.rate,
                    )
                    output.put_nowait(funding_info_update)
                await self._sleep(CONSTANTS.FUNDING_RATE_UPDATE_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public funding info updates from exchange")
                await self._sleep(CONSTANTS.FUNDING_RATE_UPDATE_INTERVAL_SECONDS)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse funding info WebSocket message.

        Note: We use polling instead of WebSocket for funding info since Backpack
        doesn't have a dedicated funding info channel. This is a no-op.
        """
        pass

    def _next_funding_time(self) -> int:
        """
        Calculate the next funding settlement timestamp.

        Backpack perpetuals settle funding every 8 hours at 00:00, 08:00, and 16:00 UTC.
        """
        current_time = time.time()
        # 8 hours in seconds
        funding_interval = 8 * 60 * 60
        # Calculate next funding time
        next_funding = ((int(current_time) // funding_interval) + 1) * funding_interval
        return next_funding
