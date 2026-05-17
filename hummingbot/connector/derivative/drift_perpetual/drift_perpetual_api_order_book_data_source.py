import asyncio
import sys
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hummingbot.connector.derivative.drift_perpetual import (
    drift_perpetual_constants as CONSTANTS,
    drift_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_derivative import DriftPerpetualDerivative


class DriftPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    """
    Order book / trades / funding for Drift perpetuals.

    Drift's order book is NOT served by the gateway; it comes from the
    hosted DLOB server (mainnet wss://dlob.drift.trade/ws). The DLOB is a
    **snapshot stream** — dlob-server's `dlob-publisher` periodically
    snapshots the book to Redis and `ws-manager` pushes the latest full
    book — so there is no incremental-diff protocol; every order-book
    message is treated as a SNAPSHOT.

    Verified schema (driftpy + dlob-server sources, 2026-05-17):
      - subscribe: {"type":"subscribe","marketType":"perp",
                    "channel":"orderbook"|"trades","market":"SOL-PERP"}
      - envelope:  {"channel": <str>, "data": <payload>}  (wsClient.ts)
      - L2 payload (driftpy dlob/orderbook_levels.py):
            {"bids":[{"price":int,"size":int,"sources":{}}],
             "asks":[...], "slot":int}
        price scaled by PRICE_PRECISION(1e6), size by BASE_PRECISION(1e9).

    Documented residual assumptions (isolated, schema-confirm at
    integration — same gate as the project's other connector PRs):
      [A1] exact nesting of the L2 book inside `message["data"]`
      [A2] trades payload shape inside `data` for channel "trades"
      [A3] Data API base/path for historical funding (see get_funding_info)
    """

    FULL_ORDER_BOOK_RESET_DELTA_SECONDS = sys.maxsize

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "DriftPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._nonce_provider = NonceCreator.for_microseconds()

    def _time(self) -> float:
        return time.time()

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    # --- scaling helpers (driftpy-verified precision) ---
    @staticmethod
    def _scaled_price(raw: Any) -> Decimal:
        return Decimal(str(raw)) / Decimal(CONSTANTS.PRICE_PRECISION)

    @staticmethod
    def _scaled_size(raw: Any) -> Decimal:
        return Decimal(str(raw)) / Decimal(CONSTANTS.BASE_PRECISION)

    @classmethod
    def _levels(cls, entries: List[Dict[str, Any]]) -> List[Tuple[Decimal, Decimal]]:
        return [(cls._scaled_price(e["price"]), cls._scaled_size(e["size"])) for e in entries or []]

    def _get_bids_and_asks(
        self, book: Dict[str, Any]
    ) -> Tuple[List[Tuple[Decimal, Decimal]], List[Tuple[Decimal, Decimal]]]:
        return self._levels(book.get("bids", [])), self._levels(book.get("asks", []))

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.DRIFT_DLOB_WS_URL, ping_timeout=CONSTANTS.HEARTBEAT_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for channel in (CONSTANTS.WS_DLOB_CHANNEL_ORDERBOOK, CONSTANTS.WS_DLOB_CHANNEL_TRADES):
                    await ws.send(WSJSONRequest(
                        payload={
                            "type": CONSTANTS.WS_DLOB_TYPE_SUBSCRIBE,
                            "marketType": CONSTANTS.MARKET_TYPE_PERP,
                            "channel": channel,
                            "market": ex_symbol,
                        },
                        is_auth_required=False,
                    ))
            self.logger().info("Subscribed to Drift DLOB orderbook and trade channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to Drift DLOB streams.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = event_message.get("channel", "")
        if channel == CONSTANTS.WS_DLOB_CHANNEL_TRADES:
            return self._trade_messages_queue_key
        if channel == CONSTANTS.WS_DLOB_CHANNEL_ORDERBOOK:
            # snapshot stream — no diff queue
            return self._snapshot_messages_queue_key
        return ""

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # [A1] book is at message["data"]; treat as full snapshot.
        data = raw_message.get("data") or {}
        market = data.get("market") or raw_message.get("market")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=market)
        bids, asks = self._get_bids_and_asks(data)
        timestamp = self._time()
        update_id = data.get("slot") or self._nonce_provider.get_tracking_nonce(timestamp=timestamp)
        message_queue.put_nowait(OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"trading_pair": trading_pair, "update_id": update_id, "bids": bids, "asks": asks},
            timestamp=timestamp,
        ))

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Drift DLOB is snapshot-only; no diff protocol. Intentionally a no-op.
        return

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # [A2] trades payload shape inside data — confirm at integration.
        data = raw_message.get("data") or {}
        market = data.get("market") or raw_message.get("market")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=market)
        trades = data.get("trades", data if isinstance(data, list) else [])
        for t in trades:
            ts = float(t.get("ts", self._time()))
            side = str(t.get("side", "")).lower()
            trade_type = float(TradeType.BUY.value) if side in ("buy", "long") else float(TradeType.SELL.value)
            message_queue.put_nowait(OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content={
                    "trading_pair": trading_pair,
                    "trade_id": t.get("ts", ts),
                    "trade_type": trade_type,
                    "amount": self._scaled_size(t.get("size", 0)),
                    "price": self._scaled_price(t.get("price", 0)),
                },
                timestamp=ts,
            ))

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        ex_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.dlob_rest_url(CONSTANTS.PATH_DLOB_L2)
        book = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=CONSTANTS.RATE_LIMIT_ID_ALL,
            params={"marketType": CONSTANTS.MARKET_TYPE_PERP, "marketName": ex_symbol},
            method=RESTMethod.GET,
        )
        bids, asks = self._get_bids_and_asks(book)
        timestamp = self._time()
        update_id = book.get("slot") or self._nonce_provider.get_tracking_nonce(timestamp=timestamp)
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"trading_pair": trading_pair, "update_id": update_id, "bids": bids, "asks": asks},
            timestamp=timestamp,
        )

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        # [A3] SCHEMA-UNVERIFIED: the Data API base/path for historical &
        # predicted funding is not documented in gateway/dlob-server READMEs
        # and data.api.drift.trade returned "Cannot GET" for every probed
        # path (2026-05-17). This single method is the isolated unresolved
        # seam — to be wired against the confirmed Data API funding endpoint
        # at integration (same maintainer-CI/integration gate the project's
        # other connector PRs rely on). Mark/Index price + rate come from
        # the perp marketInfo/oracle once the funding path is confirmed.
        raise NotImplementedError(
            "Drift funding-info endpoint pending schema confirmation "
            "(Data API funding path unverified — see [A3])."
        )

    async def listen_for_funding_info(self, output: asyncio.Queue):
        # Held until get_funding_info / Data API funding path is confirmed.
        return
