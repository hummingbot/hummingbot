import asyncio
from typing import Any, Dict, List, Optional
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_utils as utils

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource

class AevoPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(self,
                 trading_pairs: List[str],
                 domain: str = "aevo",
                 api_factory: Optional[Any] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[Any] = None):
        super().__init__(trading_pairs)
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory
        self._time_synchronizer = time_synchronizer

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._get_last_traded_prices(trading_pairs)

    async def _get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        res = await self._api_factory.call_rest(
            method="GET",
            url=f"{CONSTANTS.AEVO_BASE_URL}{CONSTANTS.TICKER_PATH_URL}"
        )
        # Aevo returns list of tickers. Map 'instrument_name' to price.
        # Example response: [{"instrument_name": "ETH-PERP", "mark_price": "2000.5", ...}, ...]
        results = {}
        for market in res:
            name = market.get("instrument_name", "") # e.g., ETH-PERP
            hb_name = utils.convert_to_hb_symbol(name)
            if "mark_price" in market:
                results[hb_name] = float(market["mark_price"])
        return results

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        # Aevo Orderbook Endpoint: /order_book?instrument_name=...
        exchange_symbol = utils.convert_to_exchange_symbol(trading_pair)
        params = {"instrument_name": exchange_symbol}
        snapshot = await self._api_factory.call_rest(
            method="GET",
            url=f"{CONSTANTS.AEVO_BASE_URL}{CONSTANTS.SNAPSHOT_PATH_URL}",
            params=params
        )
        # Snapshot structure: {"bids": [[price, size], ...], "asks": ...}
        # Convert to OrderBookMessage or OrderBook object
        # Note: Hummingbot expects specific mapping, usually handled by message parser.
        # For now, we return the raw snapshot or an OrderBook object depending on base class calc.
        # Check base class: OrderBookTrackerDataSource usually returns OrderBookMessage from snapshot.
        from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
        
        timestamp = snapshot.get("timestamp", self._time_synchronizer.time() * 1e9)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(timestamp),
                "bids": snapshot.get("bids", []),
                "asks": snapshot.get("asks", [])
            },
            timestamp=timestamp * 1e-9
        )


    async def listen_for_subscriptions(self):
        ws = None
        while True:
            try:
                ws = await self._api_factory.get_ws_connection(CONSTANTS.AEVO_WS_URL)
                await ws.connect()
                
                # Subscribe to channels
                for pair in self._trading_pairs:
                    subscribe_request = {
                        "op": "subscribe",
                        "data": [
                            f"{CONSTANTS.WS_TOPIC_ORDERBOOK}:{pair}",
                            f"{CONSTANTS.WS_TOPIC_TRADES}:{pair}"
                        ]
                    }
                    await ws.send_json(subscribe_request)
                
                async for msg in ws.iter_messages():
                    if msg.data:
                        data = msg.json()
                        channel = data.get("channel")
                        
                        if channel and channel.startswith(CONSTANTS.WS_TOPIC_ORDERBOOK):
                            # Parse Order Book Snapshot/Update
                            # Aevo sends full snapshots or updates. Assuming snapshot for simplicity or parsing both via same logic if format aligns
                            payload = data.get("data", {})
                            if payload.get("type") == "snapshot":
                                order_book_message = OrderBookMessage(
                                    OrderBookMessageType.SNAPSHOT,
                                    {
                                        "trading_pair": channel.split(":")[-1],
                                        "update_id": int(payload.get("timestamp", self._time_synchronizer.time() * 1e9)),
                                        "bids": payload.get("bids", []),
                                        "asks": payload.get("asks", [])
                                    },
                                    timestamp=payload.get("timestamp", self._time_synchronizer.time() * 1e9) * 1e-9
                                )
                                self._message_queue.put_nowait(order_book_message)
                        
                        elif channel and channel.startswith(CONSTANTS.WS_TOPIC_TRADES):
                            # Parse Trades
                            payload = data.get("data", [])
                            # Payload might be a list of trades
                            for trade in payload:
                                trade_msg = OrderBookMessage(
                                    OrderBookMessageType.TRADE,
                                    {
                                        "trading_pair": channel.split(":")[-1],
                                        "trade_type": float(trade.get("amount", 0)) > 0 and 1 or 2, # 1 for Buy, 2 for Sell (approx)
                                        "trade_id": trade.get("trade_id"),
                                        "update_id": int(trade.get("timestamp", 0)),
                                        "price": trade.get("price"),
                                        "amount": trade.get("amount")
                                    },
                                    timestamp=trade.get("timestamp", self._time_synchronizer.time() * 1e9) * 1e-9
                                )
                                self._message_queue.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Log error and reconnect
                print(f"WS Error: {e}") # "Human mode" print (to be replaced by logger later)
                await asyncio.sleep(5)
            finally:
                if ws:
                    await ws.disconnect()

