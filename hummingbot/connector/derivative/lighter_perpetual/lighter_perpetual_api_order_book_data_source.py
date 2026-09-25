import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_utils import next_funding_timestamp_seconds
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_order_book import LighterOrderBook
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
        LighterPerpetualDerivative,
    )


class LighterPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "LighterPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._order_book_create_function = lambda: LighterOrderBook()

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        market = self._connector.market_info_for_trading_pair(trading_pair)
        response = await self._connector._api_get(
            path_url=CONSTANTS.FUNDING_RATES_PATH_URL,
            params={"market_id": market.market_id},
        )

        funding_rate = self._funding_rate_from_response(response=response, market_id=market.market_id)
        mark_price = self._safe_decimal(market.raw_info.get("mark_price", market.raw_info.get("last_trade_price", "0")))
        index_price = self._safe_decimal(market.raw_info.get("index_price", market.raw_info.get("last_trade_price", mark_price)))

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=index_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=self._next_funding_utc_timestamp(),
            rate=funding_rate,
        )

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        market = self._connector.market_info_for_trading_pair(trading_pair)
        return await self._connector._api_get(
            path_url=CONSTANTS.SNAPSHOT_PATH_URL,
            params={
                "market_id": market.market_id,
                "limit": CONSTANTS.ORDER_BOOK_SNAPSHOT_LIMIT,
            },
        )

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair=trading_pair)
        return LighterOrderBook.snapshot_message_from_rest(snapshot, trading_pair=trading_pair)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.wss_url(domain=self._domain),
            ping_timeout=CONSTANTS.PUBLIC_WS_PING_INTERVAL,
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                market = self._connector.market_info_for_trading_pair(trading_pair)
                await ws.send(
                    WSJSONRequest(
                        payload={
                            "type": "subscribe",
                            "channel": f"{CONSTANTS.ORDER_BOOK_CHANNEL}/{market.market_id}",
                        }
                    )
                )
                await ws.send(
                    WSJSONRequest(
                        payload={
                            "type": "subscribe",
                            "channel": f"{CONSTANTS.TRADE_CHANNEL}/{market.market_id}",
                        }
                    )
                )
                await ws.send(
                    WSJSONRequest(
                        payload={
                            "type": "subscribe",
                            "channel": f"{CONSTANTS.MARKET_STATS_CHANNEL}/{market.market_id}",
                        }
                    )
                )
            self.logger().info("Subscribed to Lighter public order book, trade, and market stats channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to Lighter public streams.")
            raise

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot subscribe to {trading_pair}: WebSocket not connected")
            return False

        try:
            market = self._connector.market_info_for_trading_pair(trading_pair)
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "type": "subscribe",
                        "channel": f"{CONSTANTS.ORDER_BOOK_CHANNEL}/{market.market_id}",
                    }
                )
            )
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "type": "subscribe",
                        "channel": f"{CONSTANTS.TRADE_CHANNEL}/{market.market_id}",
                    }
                )
            )
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "type": "subscribe",
                        "channel": f"{CONSTANTS.MARKET_STATS_CHANNEL}/{market.market_id}",
                    }
                )
            )
            self.add_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error subscribing to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot unsubscribe from {trading_pair}: WebSocket not connected")
            return False

        try:
            market = self._connector.market_info_for_trading_pair(trading_pair)
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "type": "unsubscribe",
                        "channel": f"{CONSTANTS.ORDER_BOOK_CHANNEL}/{market.market_id}",
                    }
                )
            )
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "type": "unsubscribe",
                        "channel": f"{CONSTANTS.TRADE_CHANNEL}/{market.market_id}",
                    }
                )
            )
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "type": "unsubscribe",
                        "channel": f"{CONSTANTS.MARKET_STATS_CHANNEL}/{market.market_id}",
                    }
                )
            )
            self.remove_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error unsubscribing from {trading_pair}")
            return False

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = str(event_message.get("channel", ""))
        message_type = str(event_message.get("type", ""))

        if channel.startswith(f"{CONSTANTS.ORDER_BOOK_CHANNEL}:"):
            if message_type.startswith("subscribed/"):
                return self._snapshot_messages_queue_key
            return self._diff_messages_queue_key
        if channel.startswith(f"{CONSTANTS.TRADE_CHANNEL}:"):
            return self._trade_messages_queue_key
        if channel.startswith(f"{CONSTANTS.MARKET_STATS_CHANNEL}:"):
            return self._funding_info_messages_queue_key
        return ""

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        market_id = int(str(raw_message["channel"]).split(":")[1])
        trading_pair = self._connector.market_info_for_market_id(market_id).trading_pair
        message_queue.put_nowait(
            LighterOrderBook.snapshot_message_from_ws(raw_message, trading_pair=trading_pair)
        )

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        market_id = int(str(raw_message["channel"]).split(":")[1])
        trading_pair = self._connector.market_info_for_market_id(market_id).trading_pair
        message_queue.put_nowait(
            LighterOrderBook.diff_message_from_ws(raw_message, trading_pair=trading_pair)
        )

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        market_id = int(str(raw_message["channel"]).split(":")[1])
        trading_pair = self._connector.market_info_for_market_id(market_id).trading_pair
        for trade in raw_message.get("trades", []):
            message_queue.put_nowait(
                LighterOrderBook.trade_message_from_ws(trade, trading_pair=trading_pair)
            )

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        market_stats = raw_message.get("market_stats", raw_message)
        market_id = market_stats.get("market_id")
        if market_id is None:
            channel = str(raw_message.get("channel", ""))
            if ":" in channel:
                _, market_id = channel.split(":", 1)

        if market_id is None:
            return

        try:
            market_id = int(market_id)
        except (TypeError, ValueError):
            return

        market = self._connector.market_info_for_market_id(market_id)

        rate = market_stats.get("current_funding_rate", market_stats.get("rate", market_stats.get("funding_rate")))
        if rate is None:
            rate = self._funding_rate_from_response(response=market_stats, market_id=market_id)
        else:
            rate = self._safe_decimal(rate)

        next_funding_timestamp = self._next_funding_utc_timestamp()
        funding_timestamp = market_stats.get("funding_timestamp")
        if funding_timestamp is not None:
            next_funding_timestamp = next_funding_timestamp_seconds(int(funding_timestamp))

        info_update = FundingInfoUpdate(
            trading_pair=market.trading_pair,
            rate=rate,
            next_funding_utc_timestamp=next_funding_timestamp,
        )

        if "mark_price" in market_stats:
            info_update.mark_price = self._safe_decimal(market_stats["mark_price"])
        if "index_price" in market_stats:
            info_update.index_price = self._safe_decimal(market_stats["index_price"])

        message_queue.put_nowait(info_update)

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        if event_message.get("type") == "connected":
            return
        if event_message.get("type") == "ping":
            await websocket_assistant.send(WSJSONRequest(payload={"type": "pong"}))
            return
        if event_message.get("error") is not None:
            raise IOError(f"Lighter public websocket error: {event_message['error']}")

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        ping_task = asyncio.create_task(self._app_ping_loop(websocket_assistant))
        try:
            await super()._process_websocket_messages(websocket_assistant=websocket_assistant)
        finally:
            ping_task.cancel()

    async def _app_ping_loop(self, websocket_assistant: WSAssistant):
        try:
            while True:
                await asyncio.sleep(CONSTANTS.PUBLIC_WS_PING_INTERVAL)
                await websocket_assistant.send(WSJSONRequest(payload={"type": "ping"}))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    def _next_funding_utc_timestamp(self) -> int:
        now = int(time.time())
        interval = int(CONSTANTS.FUNDING_INTERVAL_SECONDS)
        return ((now // interval) + 1) * interval

    @staticmethod
    def _safe_decimal(value: Any) -> Decimal:
        return Decimal(str(value))

    def _funding_rate_from_response(self, response: Any, market_id: int) -> Decimal:
        direct_rate = None
        if isinstance(response, dict):
            direct_rate = response.get("rate", response.get("funding_rate"))
        if direct_rate is not None:
            return self._safe_decimal(direct_rate)

        items: Any = response
        if isinstance(response, dict):
            items = response.get("funding_rates", response.get("rates", response.get("data", [])))

        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_market_id = item.get("market_id")
                if item_market_id is None:
                    continue
                try:
                    if int(item_market_id) != market_id:
                        continue
                except (TypeError, ValueError):
                    continue
                candidate = item.get("rate", item.get("funding_rate"))
                if candidate is not None:
                    return self._safe_decimal(candidate)

        return Decimal("0")
