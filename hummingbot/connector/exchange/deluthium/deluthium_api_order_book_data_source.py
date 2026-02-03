"""
Order book data source for Deluthium DEX connector.

Deluthium is RFQ-based, so instead of traditional order book depth,
we fetch indicative quotes to construct price information.
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.deluthium import (
    deluthium_constants as CONSTANTS,
    deluthium_web_utils as web_utils,
)
from hummingbot.connector.exchange.deluthium.deluthium_order_book import DeluthiumOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.deluthium.deluthium_exchange import DeluthiumExchange


class DeluthiumAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    Order book data source for Deluthium.
    
    Since Deluthium doesn't have a traditional order book (it's RFQ-based),
    this class fetches market pair data and constructs price information
    from the market overview endpoint.
    """
    
    HEARTBEAT_TIME_INTERVAL = 30.0
    ONE_HOUR = 60 * 60
    
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'DeluthiumExchange',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN
    ):
        """
        Initialize the order book data source.
        
        :param trading_pairs: List of trading pairs to track
        :param connector: The exchange connector instance
        :param api_factory: Web assistants factory for API calls
        :param domain: Domain (default: deluthium)
        """
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get last traded prices for trading pairs.
        
        :param trading_pairs: List of trading pairs
        :param domain: Domain (unused)
        :return: Dictionary of trading pair to price
        """
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Request order book snapshot (market pair data for Deluthium).
        
        IMPORTANT: Deluthium is RFQ-based and does NOT have a traditional order book.
        This method returns market price data, NOT real order book depth.
        Strategies requiring accurate bid/ask spreads or depth will not work correctly.
        
        :param trading_pair: Trading pair to get data for
        :return: Market pair data formatted as order book
        """
        # Use chain-qualified cache lookup
        pair_cache = self._connector._get_pair_cache(trading_pair)
        pair_id = pair_cache.get("pair_id")
        chain_id = pair_cache.get("chain_id", CONSTANTS.DEFAULT_CHAIN_ID)
        
        if pair_id is None:
            # Fallback: try to load markets
            await self._connector.load_markets()
            pair_cache = self._connector._get_pair_cache(trading_pair)
            pair_id = pair_cache.get("pair_id")
        
        if pair_id is None:
            self.logger().warning(
                f"Deluthium: pairId not found for {trading_pair} on chain {chain_id}. "
                f"Cannot fetch market data."
            )
            return {"bids": [], "asks": [], "trading_pair": trading_pair}
        
        # Fetch market pair data
        params = {
            "chainId": chain_id,
            "pairId": pair_id,
            "interval": "1h",
        }
        
        try:
            response = await self._connector._api_get(
                path_url=CONSTANTS.MARKET_PAIR_URL,
                params=params,
                is_auth_required=True
            )
            
            data = response.get("data", {})
            price = float(data.get("price", 0))
            
            # RFQ exchanges don't have real order book depth
            # We return mid-price with a small synthetic spread for display purposes
            # WARNING: This is NOT real market depth!
            if price > 0:
                # Create a small synthetic spread (0.1%) for display
                spread_pct = 0.001
                bid_price = price * (1 - spread_pct / 2)
                ask_price = price * (1 + spread_pct / 2)
                
                return {
                    "trading_pair": trading_pair,
                    "bids": [[bid_price, 0]],  # Size 0 indicates synthetic/unknown
                    "asks": [[ask_price, 0]],  # Size 0 indicates synthetic/unknown
                    "update_id": int(time.time() * 1000),
                    "is_synthetic": True,  # Flag to indicate this is not real depth
                }
        except Exception as e:
            self.logger().warning(f"Error fetching market pair data for {trading_pair}: {e}")
        
        return {"bids": [], "asks": [], "trading_pair": trading_pair}

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Get order book snapshot for a trading pair.
        
        :param trading_pair: Trading pair
        :return: OrderBookMessage snapshot
        """
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot["trading_pair"] = trading_pair
        snapshot_timestamp: float = time.time()
        
        snapshot_msg: OrderBookMessage = DeluthiumOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def listen_for_subscriptions(self):
        """
        Listen for subscriptions.
        
        Deluthium doesn't have WebSocket for market data, so we poll periodically.
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot_msg = await self._order_book_snapshot(trading_pair)
                        self._message_queue[self._snapshot_messages_queue_key].put_nowait(snapshot_msg)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        self.logger().warning(f"Error fetching snapshot for {trading_pair}: {e}")
                
                # Poll every 30 seconds
                await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in listen_for_subscriptions: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Determine the channel for a message.
        
        Since we don't use WebSocket, this is a placeholder.
        """
        return self._snapshot_messages_queue_key
