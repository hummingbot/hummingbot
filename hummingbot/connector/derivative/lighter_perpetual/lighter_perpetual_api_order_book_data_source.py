import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
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
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._market_id_to_trading_pair: Dict[int, str] = {}
        self._ping_task: Optional[asyncio.Task] = None

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    def _get_headers(self) -> Dict[str, str]:
        """Headers for WebSocket connections (X-Api-Key if available).
        Not used for public REST calls to avoid triggering stricter auth
        requirements on the Lighter API for main accounts."""
        headers = {}
        if self._connector.rest_api_key:
            headers["X-Api-Key"] = self._connector.rest_api_key
        return headers

    def _get_public_headers(self) -> Dict[str, str]:
        """Empty headers for public REST calls (no auth needed/wanted)."""
        return {}

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        https://docs.lighter.fi/api-documentation/api/rest-api/markets/get-orderbook

        {
            "success": true,
            "data": {
                "s": "BTC",
                "l": [
                [
                    {
                    "p": "106504",
                    "a": "0.26203",
                    "n": 1
                    },
                    {
                    "p": "106498",
                    "a": "0.29281",
                    "n": 1
                    }
                ],
                [
                    {
                    "p": "106559",
                    "a": "0.26802",
                    "n": 1
                    },
                    {
                    "p": "106564",
                    "a": "0.3002",
                    "n": 1
                    },
                ]
                ],
                "t": 1751370536325
            },
            "error": null,
            "code": null
        }
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        market_id, _, _, _ = await self._connector._get_market_spec(trading_pair)
        params = {"market_id": market_id, "limit": 250}

        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL,
            headers=self._get_public_headers()
        )

        code = response.get("code")
        is_success = response.get("success") is True
        try:
            is_success = is_success or int(code) == 200
        except Exception:
            pass

        if not is_success:
            raise ValueError(f"[get_order_book_snapshot] Failed to get order book snapshot for {trading_pair}: {response}")

        return response

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        order_book_snapshot_data = await self._request_order_book_snapshot(trading_pair)
        order_book_snapshot_timestamp = time.time()

        # Lighter returns snapshots in response["data"]["l"] where l[0]=bids and l[1]=asks.
        # Keep backward compatibility with older top-level bids/asks payloads used in tests.
        snapshot_payload = order_book_snapshot_data.get("data") or {}
        levels = snapshot_payload.get("l") or []

        if len(levels) >= 2:
            bids = [(bid.get("p"), bid.get("a")) for bid in levels[0]]
            asks = [(ask.get("p"), ask.get("a")) for ask in levels[1]]
            update_id = snapshot_payload.get("li") or 1
        else:
            bids = [
                (bid["price"], bid["remaining_base_amount"])
                for bid in order_book_snapshot_data.get("bids", [])
            ]
            asks = [
                (ask["price"], ask["remaining_base_amount"])
                for ask in order_book_snapshot_data.get("asks", [])
            ]
            update_id = 1

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }, timestamp=order_book_snapshot_timestamp)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Uses /funding-rates to get the current funding rate per symbol.
        /exchangeStats does not return mark/oracle/funding fields — those come from the WS prices stream.

        /funding-rates response (array of objects):
        [
            {"market_id": 1, "symbol": "BTC", "rate": 2.779e-05},
            ...
        ]

        Index/mark prices start at 0 here; the WS prices channel populates them after connection.
        Next funding timestamp = :00 of next hour
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        # Try to get the exchange symbol from the symbol map; fall back to the base currency if not ready yet.
        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        except Exception:
            symbol = trading_pair.split("-")[0]
        base_currency = trading_pair.split("-")[0]

        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.GET_FUNDING_RATES_PATH_URL, domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.GET_FUNDING_RATES_PATH_URL,
            headers=self._get_public_headers()
        )

        # /funding-rates returns a plain list in production. Keep legacy object parsing for backwards compatibility.
        rate_entries = response if isinstance(response, list) else (response.get("funding_rates") or response.get("data") or [])

        rate_str = "0"
        index_price_str = "0"
        mark_price_str = "0"

        for entry in rate_entries:
            entry_symbol = entry.get("symbol", "")
            if entry_symbol == symbol or entry_symbol == base_currency:
                rate_str = str(entry.get("rate") or entry.get("funding") or "0")
                # Legacy payloads may include oracle/mark in data entries.
                index_price_str = str(entry.get("oracle") or "0")
                mark_price_str = str(entry.get("mark") or "0")
                break

        # Some mock and legacy responses expose order_book_stats.
        if rate_str == "0" and isinstance(response, dict):
            legacy_entries = response.get("order_book_stats") or []
            for entry in legacy_entries:
                entry_symbol = entry.get("symbol", "")
                if entry_symbol == symbol or entry_symbol == base_currency:
                    rate_str = str(entry.get("funding") or "0")
                    index_price_str = str(entry.get("oracle") or "0")
                    mark_price_str = str(entry.get("mark") or "0")
                    break

        # Mark/index prices are typically populated by WS prices updates after startup.
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(index_price_str),
            mark_price=Decimal(mark_price_str),
            next_funding_utc_timestamp=int((time.time() // 3600 + 1) * 3600),
            rate=Decimal(rate_str),
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()

        await ws.connect(ws_url=web_utils.wss_url(self._domain), ws_headers=self._get_headers())
        self._ping_task = safe_ensure_future(self._ping_loop(ws))
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                market_id, _, _, _ = await self._connector._get_market_spec(trading_pair)
                self._market_id_to_trading_pair[market_id] = trading_pair
                await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"order_book/{market_id}"}))
                await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"trade/{market_id}"}))
                await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"market_stats/{market_id}"}))
            self.logger().info("Subscribed to public order book, trade, and market_stats channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading pairs.")
            raise

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        await super()._on_order_stream_interruption(websocket_assistant)
        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None

    async def _ping_loop(self, ws: WSAssistant):
        while True:
            try:
                await asyncio.sleep(CONSTANTS.WS_PING_INTERVAL)
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await ws.send(ping_request)
            except asyncio.CancelledError:
                raise
            except RuntimeError as e:
                if "WS is not connected" in str(e):
                    return
                raise
            except Exception:
                self.logger().warning("Error sending ping to LIGHTER WebSocket", exc_info=True)
                await asyncio.sleep(5.0)  # Wait before retrying

    @staticmethod
    def _market_id_from_channel(channel: str) -> Optional[int]:
        for separator in (":", "/"):
            if separator in channel:
                tail = channel.rsplit(separator, 1)[-1]
                try:
                    return int(tail)
                except Exception:
                    return None
        return None

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        channel = str(raw_message.get("channel", ""))
        market_id = self._market_id_from_channel(channel)
        if market_id is None:
            return
        trading_pair = self._market_id_to_trading_pair.get(market_id)
        if trading_pair is None:
            return

        order_book = raw_message.get("order_book") or {}
        snapshot_timestamp = float(raw_message.get("timestamp") or raw_message.get("last_updated_at") or 0) / 1000
        update_id = int(order_book.get("nonce") or raw_message.get("nonce") or 0)
        if update_id == 0:
            update_id = int(raw_message.get("offset") or order_book.get("offset") or raw_message.get("last_updated_at") or 0)

        snapshot_msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [(bid["price"], bid["size"]) for bid in order_book.get("bids", [])],
            "asks": [(ask["price"], ask["size"]) for ask in order_book.get("asks", [])],
        }, timestamp=snapshot_timestamp)
        message_queue.put_nowait(snapshot_msg)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        channel = str(raw_message.get("channel", ""))
        market_id = self._market_id_from_channel(channel)
        if market_id is None:
            return
        trading_pair = self._market_id_to_trading_pair.get(market_id)
        if trading_pair is None:
            return

        order_book = raw_message.get("order_book") or {}
        update_id = int(order_book.get("nonce") or raw_message.get("nonce") or 0)
        if update_id == 0:
            update_id = int(raw_message.get("offset") or order_book.get("offset") or 0)

        diff_msg = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "first_update_id": int(order_book.get("begin_nonce") or update_id),
            "update_id": update_id,
            "bids": [(bid["price"], bid["size"]) for bid in order_book.get("bids", [])],
            "asks": [(ask["price"], ask["size"]) for ask in order_book.get("asks", [])],
        }, timestamp=float(raw_message.get("timestamp") or 0) / 1000)
        message_queue.put_nowait(diff_msg)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        channel = str(raw_message.get("channel", ""))
        market_id = self._market_id_from_channel(channel)
        if market_id is None:
            return
        trading_pair = self._market_id_to_trading_pair.get(market_id)
        if trading_pair is None:
            return

        for trade_data in raw_message.get("trades", []):
            is_maker_ask = bool(trade_data.get("is_maker_ask"))
            trade_message = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value) if is_maker_ask else float(TradeType.SELL.value),
                "trade_id": trade_data.get("nonce") or raw_message.get("nonce"),
                "update_id": trade_data.get("nonce") or raw_message.get("nonce") or 0,
                "price": trade_data.get("price", "0"),
                "amount": trade_data.get("size", "0"),
            }, timestamp=float(raw_message.get("timestamp") or 0) / 1000)
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        market_stats = raw_message.get("market_stats") or {}
        if not market_stats:
            return

        channel = str(raw_message.get("channel", ""))
        market_id = self._market_id_from_channel(channel)
        if market_id is None:
            return
        trading_pair = self._market_id_to_trading_pair.get(market_id)
        if trading_pair is None:
            return

        index_price = Decimal(str(market_stats.get("index_price") or "0"))
        mark_price = Decimal(str(market_stats.get("mark_price") or "0"))
        rate = Decimal(str(market_stats.get("current_funding_rate") or "0"))
        funding_timestamp_ms = int(market_stats.get("funding_timestamp") or 0)
        next_funding_utc_timestamp = (funding_timestamp_ms // 1000) if funding_timestamp_ms > 0 else int((time.time() // 3600 + 1) * 3600)

        info_update = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=index_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=next_funding_utc_timestamp,
            rate=rate,
        )
        message_queue.put_nowait(info_update)

        self._connector.set_LIGHTER_price(
            trading_pair,
            timestamp=float(raw_message.get("timestamp") or 0) / 1000,
            index_price=index_price,
            mark_price=mark_price,
        )

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        if "channel" not in event_message:
            return ""
        event_channel = str(event_message.get("channel"))
        event_type = str(event_message.get("type", ""))
        if (
            event_channel.startswith(f"{CONSTANTS.WS_ORDER_BOOK_SNAPSHOT_CHANNEL}:")
            or event_channel.startswith(f"{CONSTANTS.WS_ORDER_BOOK_SNAPSHOT_CHANNEL}/")
        ):
            if event_type in {"subscribed/order_book", "snapshot/order_book"}:
                return self._snapshot_messages_queue_key
            if event_type == "update/order_book":
                return self._diff_messages_queue_key
            return self._snapshot_messages_queue_key
        if (
            event_channel.startswith(f"{CONSTANTS.WS_TRADES_CHANNEL}:")
            or event_channel.startswith(f"{CONSTANTS.WS_TRADES_CHANNEL}/")
        ):
            return self._trade_messages_queue_key
        if (
            event_channel.startswith(f"{CONSTANTS.WS_MARKET_STATS_CHANNEL}:")
            or event_channel.startswith(f"{CONSTANTS.WS_MARKET_STATS_CHANNEL}/")
        ):
            return self._funding_info_messages_queue_key
        return ""

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False
        try:
            market_id, _, _, _ = await self._connector._get_market_spec(trading_pair)
            self._market_id_to_trading_pair[market_id] = trading_pair
            self.add_trading_pair(trading_pair)
            await self._ws_assistant.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"order_book/{market_id}"}))
            await self._ws_assistant.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"trade/{market_id}"}))
            await self._ws_assistant.send(WSJSONRequest(payload={"type": "subscribe", "channel": f"market_stats/{market_id}"}))
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error subscribing to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False
        try:
            market_id, _, _, _ = await self._connector._get_market_spec(trading_pair)
            await self._ws_assistant.send(WSJSONRequest(payload={"type": "unsubscribe", "channel": f"order_book/{market_id}"}))
            await self._ws_assistant.send(WSJSONRequest(payload={"type": "unsubscribe", "channel": f"trade/{market_id}"}))
            await self._ws_assistant.send(WSJSONRequest(payload={"type": "unsubscribe", "channel": f"market_stats/{market_id}"}))
            self._market_id_to_trading_pair.pop(market_id, None)
            self.remove_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error unsubscribing from {trading_pair}")
            return False
