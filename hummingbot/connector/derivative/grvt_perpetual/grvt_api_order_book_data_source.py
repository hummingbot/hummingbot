import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_derivative import GrvtDerivative


class GrvtAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "GrvtDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(CONSTANTS.INSTRUMENTS_PATH_URL, domain=domain or self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.INSTRUMENTS_PATH_URL,
        )
        rows = self._extract_rows(response)
        prices: Dict[str, float] = {}
        for row in rows:
            ex_symbol = str(row.get("symbol") or row.get("market") or row.get("instrument") or "")
            if not ex_symbol:
                continue
            trading_pair = await self._to_hb_trading_pair(ex_symbol)
            if trading_pair not in trading_pairs:
                continue
            for field in ("lastPrice", "markPrice", "price"):
                if field in row:
                    prices[trading_pair] = float(row[field])
                    break
        return prices

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol = await self._to_exchange_symbol(trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(CONSTANTS.FUNDING_INFO_PATH_URL, domain=self._domain),
            method=RESTMethod.GET,
            params={"market": symbol},
            throttler_limit_id=CONSTANTS.FUNDING_INFO_PATH_URL,
        )
        payload = self._extract_data(response)
        next_ts = self._next_funding_time()
        if isinstance(payload, dict):
            for candidate in ("nextFundingTime", "nextFundingTimestamp", "fundingTime"):
                if candidate in payload:
                    next_ts = int(float(payload[candidate])) if float(payload[candidate]) > 1e11 else int(float(payload[candidate]) * 1e3)
                    next_ts = int(next_ts / 1000)
                    break
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(self._extract_numeric(payload, ["indexPrice", "oraclePrice", "index"], 0))),
            mark_price=Decimal(str(self._extract_numeric(payload, ["markPrice", "mark", "price"], 0))),
            next_funding_utc_timestamp=next_ts,
            rate=Decimal(str(self._extract_numeric(payload, ["fundingRate", "rate"], 0))),
        )

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        symbol = await self._to_exchange_symbol(trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url=web_utils.public_rest_url(CONSTANTS.ORDER_BOOK_PATH_URL, domain=self._domain),
            method=RESTMethod.GET,
            params={"market": symbol, "depth": 200},
            throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
        )

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        response = await self._request_order_book_snapshot(trading_pair=trading_pair)
        data = self._extract_data(response)
        ts = int(self._extract_numeric(data, ["timestamp", "time", "ts"], int(self._time() * 1000)))
        if ts < 10**11:
            ts = int(ts * 1000)
        bids = self._parse_levels(data.get("bids", []))
        asks = self._parse_levels(data.get("asks", []))
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": ts,
                "bids": bids,
                "asks": asks,
            },
            timestamp=ts / 1000.0,
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain), ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._to_exchange_symbol(trading_pair=trading_pair)
                payload = {
                    "method": "subscribe",
                    "channels": [
                        f"{CONSTANTS.WS_ORDER_BOOK_CHANNEL}:{symbol}",
                        f"{CONSTANTS.WS_TRADES_CHANNEL}:{symbol}",
                        f"{CONSTANTS.WS_FUNDING_CHANNEL}:{symbol}",
                    ],
                }
                await ws.send(WSJSONRequest(payload=payload))
            self.logger().info("Subscribed to GRVT public channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error subscribing to GRVT channels.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = str(event_message.get("channel") or event_message.get("topic") or "").lower()
        event_type = str(event_message.get("type") or "").lower()
        if CONSTANTS.WS_ORDER_BOOK_CHANNEL in channel:
            if event_type in {"snapshot", "partial", "l2snapshot"}:
                return self._snapshot_messages_queue_key
            return self._diff_messages_queue_key
        if CONSTANTS.WS_TRADES_CHANNEL in channel:
            return self._trade_messages_queue_key
        if CONSTANTS.WS_FUNDING_CHANNEL in channel:
            return self._funding_info_messages_queue_key
        return ""

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = self._extract_data(raw_message)
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            ex_symbol = str(row.get("symbol") or row.get("market") or row.get("instrument") or "")
            if not ex_symbol:
                continue
            trading_pair = await self._to_hb_trading_pair(ex_symbol)
            side = str(row.get("side") or "").lower()
            trade_type = float(TradeType.BUY.value if side == "buy" else TradeType.SELL.value)
            timestamp_ms = int(self._extract_numeric(row, ["timestamp", "time", "ts"], int(self._time() * 1000)))
            if timestamp_ms < 10**11:
                timestamp_ms *= 1000
            message_queue.put_nowait(
                OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content={
                        "trading_pair": trading_pair,
                        "trade_type": trade_type,
                        "trade_id": row.get("tradeId") or row.get("id") or timestamp_ms,
                        "update_id": timestamp_ms,
                        "price": float(self._extract_numeric(row, ["price", "tradePrice"], 0)),
                        "amount": float(self._extract_numeric(row, ["size", "qty", "amount"], 0)),
                    },
                    timestamp=timestamp_ms / 1000.0,
                )
            )

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = self._extract_data(raw_message)
        ex_symbol = str(data.get("symbol") or data.get("market") or data.get("instrument") or "")
        if not ex_symbol:
            return
        trading_pair = await self._to_hb_trading_pair(ex_symbol)
        ts = int(self._extract_numeric(data, ["timestamp", "time", "ts"], int(self._time() * 1000)))
        if ts < 10**11:
            ts *= 1000
        message_queue.put_nowait(
            OrderBookMessage(
                message_type=OrderBookMessageType.DIFF,
                content={
                    "trading_pair": trading_pair,
                    "update_id": ts,
                    "bids": self._parse_levels(data.get("bids", [])),
                    "asks": self._parse_levels(data.get("asks", [])),
                },
                timestamp=ts / 1000.0,
            )
        )

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = self._extract_data(raw_message)
        ex_symbol = str(data.get("symbol") or data.get("market") or data.get("instrument") or "")
        if not ex_symbol:
            return
        trading_pair = await self._to_hb_trading_pair(ex_symbol)
        ts = int(self._extract_numeric(data, ["timestamp", "time", "ts"], int(self._time() * 1000)))
        if ts < 10**11:
            ts *= 1000
        message_queue.put_nowait(
            OrderBookMessage(
                message_type=OrderBookMessageType.SNAPSHOT,
                content={
                    "trading_pair": trading_pair,
                    "update_id": ts,
                    "bids": self._parse_levels(data.get("bids", [])),
                    "asks": self._parse_levels(data.get("asks", [])),
                },
                timestamp=ts / 1000.0,
            )
        )

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = self._extract_data(raw_message)
        ex_symbol = str(data.get("symbol") or data.get("market") or data.get("instrument") or "")
        if not ex_symbol:
            return
        trading_pair = await self._to_hb_trading_pair(ex_symbol)
        message_queue.put_nowait(
            FundingInfoUpdate(
                trading_pair=trading_pair,
                index_price=Decimal(str(self._extract_numeric(data, ["indexPrice", "oraclePrice", "index"], 0))),
                mark_price=Decimal(str(self._extract_numeric(data, ["markPrice", "mark", "price"], 0))),
                next_funding_utc_timestamp=self._next_funding_time(),
                rate=Decimal(str(self._extract_numeric(data, ["fundingRate", "rate"], 0))),
            )
        )

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False
        try:
            symbol = await self._to_exchange_symbol(trading_pair)
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "method": "subscribe",
                        "channels": [
                            f"{CONSTANTS.WS_ORDER_BOOK_CHANNEL}:{symbol}",
                            f"{CONSTANTS.WS_TRADES_CHANNEL}:{symbol}",
                            f"{CONSTANTS.WS_FUNDING_CHANNEL}:{symbol}",
                        ],
                    }
                )
            )
            self.add_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Failed to subscribe to %s", trading_pair)
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False
        try:
            symbol = await self._to_exchange_symbol(trading_pair)
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload={
                        "method": "unsubscribe",
                        "channels": [
                            f"{CONSTANTS.WS_ORDER_BOOK_CHANNEL}:{symbol}",
                            f"{CONSTANTS.WS_TRADES_CHANNEL}:{symbol}",
                            f"{CONSTANTS.WS_FUNDING_CHANNEL}:{symbol}",
                        ],
                    }
                )
            )
            self.remove_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Failed to unsubscribe from %s", trading_pair)
            return False

    async def _to_exchange_symbol(self, trading_pair: str) -> str:
        symbol = self._connector.exchange_symbol_associated_to_pair(trading_pair)
        if asyncio.iscoroutine(symbol):
            symbol = await symbol
        return str(symbol)

    async def _to_hb_trading_pair(self, exchange_symbol: str) -> str:
        if hasattr(self._connector, "trading_pair_associated_to_exchange_symbol"):
            pair = self._connector.trading_pair_associated_to_exchange_symbol(exchange_symbol)
            if asyncio.iscoroutine(pair):
                pair = await pair
            if pair:
                return str(pair)
        if hasattr(self._connector, "convert_from_exchange_trading_pair"):
            return str(self._connector.convert_from_exchange_trading_pair(exchange_symbol))
        return str(exchange_symbol)

    def _extract_data(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            for key in ("data", "result", "payload"):
                if key in payload:
                    return payload[key]
        return payload

    def _extract_rows(self, payload: Any) -> List[Dict[str, Any]]:
        data = self._extract_data(payload)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for key in ("items", "rows", "markets", "instruments"):
                if key in data and isinstance(data[key], list):
                    return [x for x in data[key] if isinstance(x, dict)]
            return [data]
        return []

    def _extract_numeric(self, payload: Any, keys: List[str], default: Any) -> Any:
        if isinstance(payload, dict):
            for key in keys:
                if key in payload and payload[key] is not None:
                    return payload[key]
        return default

    def _parse_levels(self, levels: Any) -> List[List[float]]:
        parsed: List[List[float]] = []
        if not isinstance(levels, list):
            return parsed
        for level in levels:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                parsed.append([float(level[0]), float(level[1])])
            elif isinstance(level, dict):
                price = self._extract_numeric(level, ["price", "px", "p"], None)
                size = self._extract_numeric(level, ["size", "qty", "amount", "sz", "q"], None)
                if price is not None and size is not None:
                    parsed.append([float(price), float(size)])
        return parsed

    def _next_funding_time(self) -> int:
        return int(((time.time() // 3600) + 1) * 3600)
