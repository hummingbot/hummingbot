import asyncio
import time
from typing import Any, Dict, List, Optional

import aiohttp

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils as web_utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class DecibelPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    Provides order book data for Decibel Perpetual markets via REST polling.

    Decibel does not have a documented WebSocket API, so all data is fetched
    via REST polling at regular intervals.
    """

    _logger: Optional[HummingbotLogger] = None

    ORDERBOOK_SNAPSHOT_INTERVAL = 10.0  # seconds between snapshots
    TRADES_POLL_INTERVAL = 5.0          # seconds between trade polls
    FUNDING_RATE_INTERVAL = 60.0        # seconds between funding rate polls

    def __init__(
        self,
        trading_pairs: List[str],
        connector,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs = trading_pairs
        self._base_url = web_utils.get_rest_url(domain)
        self._last_trade_ids: Dict[str, str] = {}

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get auth headers from connector."""
        headers: Dict[str, str] = {}
        api_key = getattr(self._connector, "_api_key", None)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        """Fetch last traded prices for a list of trading pairs."""
        result: Dict[str, float] = {}
        base_url = web_utils.get_rest_url(domain or self._domain)
        headers = self._get_auth_headers()

        async with aiohttp.ClientSession() as session:
            for trading_pair in trading_pairs:
                try:
                    exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                    async with session.get(
                        f"{base_url}{CONSTANTS.GET_MARKET_PRICES_PATH_URL}",
                        params={"market": exchange_symbol},
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        data = await resp.json()
                        mark_price = data.get("mark_px") or data.get("price") or data.get("mark_price")
                        if mark_price:
                            result[trading_pair] = float(mark_price)
                except Exception:
                    self.logger().warning(f"Could not fetch price for {trading_pair}", exc_info=False)
        return result

    async def _get_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """Fetch order book snapshot via REST."""
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        headers = self._get_auth_headers()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self._base_url}{CONSTANTS.GET_MARKET_PRICES_PATH_URL}",
                params={"market": exchange_symbol},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return await resp.json()

    async def get_snapshot(self, trading_pair: str, limit: int = 1000) -> Dict[str, Any]:
        """Public wrapper for order book snapshot."""
        return await self._get_order_book_snapshot(trading_pair)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """Fetch snapshot and wrap in an OrderBookMessage."""
        data = await self._get_order_book_snapshot(trading_pair)
        snapshot_timestamp = time.time()

        bids = []
        asks = []

        # Decibel price response may contain bids/asks arrays
        for bid in data.get("bids", []):
            if isinstance(bid, (list, tuple)) and len(bid) >= 2:
                bids.append([float(bid[0]), float(bid[1])])
            elif isinstance(bid, dict):
                bids.append([float(bid.get("price", 0)), float(bid.get("size", 0))])

        for ask in data.get("asks", []):
            if isinstance(ask, (list, tuple)) and len(ask) >= 2:
                asks.append([float(ask[0]), float(ask[1])])
            elif isinstance(ask, dict):
                asks.append([float(ask.get("price", 0)), float(ask.get("size", 0))])

        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": int(snapshot_timestamp * 1000),
                "bids": bids,
                "asks": asks,
            },
            timestamp=snapshot_timestamp,
        )

    async def listen_for_subscriptions(self):
        """
        Decibel does not have a WebSocket API, so we poll REST endpoints
        at regular intervals to simulate real-time data.
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot_msg = await self._order_book_snapshot(trading_pair)
                        self._message_queue[self._snapshot_messages_queue_key].put_nowait(snapshot_msg)
                    except Exception:
                        self.logger().exception(f"Error fetching snapshot for {trading_pair}")
                await asyncio.sleep(self.ORDERBOOK_SNAPSHOT_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error in listen_for_subscriptions")
                await asyncio.sleep(self.ORDERBOOK_SNAPSHOT_INTERVAL)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Decibel does not provide incremental diffs; use snapshots instead.
        This method remains a no-op to satisfy the interface.
        """
        while True:
            await asyncio.sleep(60.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Periodically fetch full order book snapshots and push to output queue."""
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot_msg = await self._order_book_snapshot(trading_pair)
                        await output.put(snapshot_msg)
                    except Exception:
                        self.logger().exception(f"Snapshot error for {trading_pair}")
                await asyncio.sleep(self.ORDERBOOK_SNAPSHOT_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error in listen_for_order_book_snapshots")
                await asyncio.sleep(self.ORDERBOOK_SNAPSHOT_INTERVAL)

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Poll recent trades and push new ones to the output queue."""
        headers = self._get_auth_headers()

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    for trading_pair in self._trading_pairs:
                        try:
                            exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                            async with session.get(
                                f"{self._base_url}{CONSTANTS.GET_RECENT_TRADES_PATH_URL}",
                                params={"market": exchange_symbol, "limit": 50},
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=10),
                            ) as resp:
                                data = await resp.json()
                                trades = data if isinstance(data, list) else data.get("trades", [])

                                last_id = self._last_trade_ids.get(trading_pair, "")

                                for trade in trades:
                                    trade_id = str(trade.get("trade_id", ""))
                                    if trade_id == last_id:
                                        break

                                    trade_msg = OrderBookMessage(
                                        message_type=OrderBookMessageType.TRADE,
                                        content={
                                            "trading_pair": trading_pair,
                                            "trade_type": (
                                                1.0 if trade.get("is_buyer_maker", False) else 2.0
                                            ),
                                            "trade_id": trade_id,
                                            "update_id": int(time.time() * 1000),
                                            "price": float(trade.get("price", 0)),
                                            "amount": float(trade.get("size", trade.get("amount", 0))),
                                        },
                                        timestamp=float(trade.get("timestamp", time.time() * 1000)) / 1000,
                                    )
                                    await output.put(trade_msg)

                                if trades:
                                    self._last_trade_ids[trading_pair] = str(
                                        trades[0].get("trade_id", "")
                                    )
                        except Exception:
                            self.logger().exception(f"Error fetching trades for {trading_pair}")

                await asyncio.sleep(self.TRADES_POLL_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error in listen_for_trades")
                await asyncio.sleep(self.TRADES_POLL_INTERVAL)

    async def get_funding_info(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """
        Fetch funding rate information for a trading pair.

        :return: Dict with funding_rate and mark_price fields, or None on error.
        """
        try:
            exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
            headers = self._get_auth_headers()

            async with aiohttp.ClientSession() as session:
                # Get current price / mark price
                async with session.get(
                    f"{self._base_url}{CONSTANTS.GET_MARKET_PRICES_PATH_URL}",
                    params={"market": exchange_symbol},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    price_data = await resp.json()

                # Get funding rate history
                async with session.get(
                    f"{self._base_url}{CONSTANTS.GET_USER_FUNDING_HISTORY_PATH_URL}",
                    params={"market": exchange_symbol, "limit": 1},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    funding_data = await resp.json()

            funding_rates = (
                funding_data
                if isinstance(funding_data, list)
                else funding_data.get("funding_rates", [])
            )
            latest_rate = funding_rates[0] if funding_rates else {}

            return {
                "trading_pair": trading_pair,
                "index_price": float(price_data.get("index_px", price_data.get("price", 0))),
                "mark_price": float(price_data.get("mark_px", price_data.get("price", 0))),
                "rate": float(latest_rate.get("funding_rate", 0)),
                "next_funding_utc_timestamp": float(latest_rate.get("next_funding_time", 0)),
            }
        except Exception:
            self.logger().exception(f"Error fetching funding info for {trading_pair}")
            return None
