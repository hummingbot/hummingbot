"""
Polymarket API data source for event namespace.
Handles REST API interactions for markets, orders, and positions.
"""

import hashlib
from decimal import Decimal
from typing import Any, Dict, List, Optional

import aiohttp

try:
    from py_clob_client.clob_types import AssetType, BalanceAllowanceParams, MarketOrderArgs, OrderArgs
    PY_CLOB_CLIENT_AVAILABLE = True
except ImportError:
    PY_CLOB_CLIENT_AVAILABLE = False
    BalanceAllowanceParams = None
    AssetType = None
    OrderArgs = None
    MarketOrderArgs = None

from hummingbot.core.data_type.common import EventMarketInfo, EventPosition, EventResolution, OutcomeInfo, OutcomeType
from hummingbot.core.data_type.event_pair import parse_event_trading_pair
from hummingbot.logger import HummingbotLogger

from .polymarket_auth import PolymarketAuth
from .polymarket_constants import MARKETS_URL, POSITIONS_URL, REQUEST_TIMEOUT, TICKER_URL


class PolymarketAPIDataSource:
    """
    API data source for Polymarket REST interactions.
    Handles markets, order books, positions, and balances.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, trading_pairs: List[str], auth: Optional[PolymarketAuth] = None):
        self._trading_pairs = trading_pairs
        self._auth = auth
        self._session: Optional[aiohttp.ClientSession] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            )
        return self._session

    async def close_session(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _api_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        auth_required: bool = False
    ) -> Dict[str, Any]:
        """Make API request with optional authentication."""

        session = await self.get_session()
        headers = {"Content-Type": "application/json"}

        if auth_required and self._auth:
            headers.update(self._auth.get_headers())

        try:
            async with session.request(method, url, params=params, json=data, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"API request failed: {response.status} - {error_text}")
        except Exception as e:
            self.logger().error(f"API request error: {e}")
            raise

    async def get_active_markets(self) -> List[EventMarketInfo]:
        """Fetch active prediction markets."""
        try:
            response = await self._api_request("GET", MARKETS_URL)
            markets = []

            for market_data in response.get("data", []):
                market_info = self._parse_market_data(market_data)
                if market_info:
                    markets.append(market_info)

            return markets

        except Exception as e:
            self.logger().error(f"Error fetching active markets: {e}")
            return []

    async def get_market_info(self, market_id: str) -> Optional[EventMarketInfo]:
        """Get information about a specific market."""
        try:
            url = f"{MARKETS_URL}/{market_id}"
            response = await self._api_request("GET", url)

            if "data" in response:
                return self._parse_market_data(response["data"])

        except Exception as e:
            self.logger().error(f"Error fetching market {market_id}: {e}")

        return None

    async def get_order_book_snapshot(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """Get order book snapshot using SDK only."""
        if not self._auth or not self._auth.client:
            raise RuntimeError("SDK authentication not available for order book retrieval")

        # Parse trading pair: MARKET-YES-USDC -> (market_id, outcome, quote)
        market_id, outcome, quote = parse_event_trading_pair(trading_pair)

        # Get token ID for this outcome
        token_id = self._get_token_id(market_id, outcome.name)

        # Use SDK method only
        await self._auth.ensure_initialized()
        orderbook = self._auth.get_order_book(token_id)

        return {
            "bids": [[float(bid.price), float(bid.size)] for bid in (orderbook.bids or [])],
            "asks": [[float(ask.price), float(ask.size)] for ask in (orderbook.asks or [])],
            "timestamp": orderbook.timestamp,
            "market": orderbook.market,
            "asset_id": orderbook.asset_id
        }

    async def get_ticker_data(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """Get ticker data for trading pair."""
        try:
            market_id, outcome, quote = parse_event_trading_pair(trading_pair)
            params = {"token_id": self._get_token_id(market_id, outcome.name)}
            response = await self._api_request("GET", TICKER_URL, params=params)
            return response.get("data")

        except Exception as e:
            self.logger().error(f"Error fetching ticker for {trading_pair}: {e}")
            return None

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        """Get last traded prices for trading pairs."""
        prices = {}

        for trading_pair in trading_pairs:
            try:
                ticker = await self.get_ticker_data(trading_pair)
                if ticker and "last_price" in ticker:
                    prices[trading_pair] = float(ticker["last_price"])
            except Exception as e:
                self.logger().error(f"Error fetching price for {trading_pair}: {e}")

        return prices

    async def get_account_positions(self) -> List[EventPosition]:
        """Get current account positions."""
        if not self._auth:
            return []

        try:
            response = await self._api_request("GET", POSITIONS_URL, auth_required=True)
            positions = []

            for position_data in response.get("data", []):
                position = self._parse_position_data(position_data)
                if position:
                    positions.append(position)

            return positions

        except Exception as e:
            self.logger().error(f"Error fetching positions: {e}")
            return []

    async def get_account_balances(self) -> Dict[str, Decimal]:
        """Get account balances using SDK only."""
        if not PY_CLOB_CLIENT_AVAILABLE:
            self.logger().error("py-clob-client is not installed. Run: pip install py-clob-client")
            return {"USDC": Decimal("0")}

        if not self._auth:
            raise RuntimeError("SDK authentication not available for balance retrieval")

        await self._auth.ensure_initialized()

        balances = {}

        # Get USDC balance using SDK
        usdc_balance = self._auth.get_balance_allowance(
            params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        )
        balances["USDC"] = Decimal(str(usdc_balance.get("balance", "0")))

        # Get conditional token balances for trading pairs using SDK
        for trading_pair in self._trading_pairs:
            market_id, outcome, quote = parse_event_trading_pair(trading_pair)
            token_id = self._get_token_id(market_id, outcome.name)

            conditional_balance = self._auth.get_balance_allowance(
                params=BalanceAllowanceParams(
                    asset_type=AssetType.CONDITIONAL,
                    token_id=token_id
                )
            )

            balance_key = f"{market_id}-{outcome.name}"
            balances[balance_key] = Decimal(str(conditional_balance.get("balance", "0")))

        return balances

    async def get_active_markets_sdk(self) -> List[EventMarketInfo]:
        """Get active markets using SDK only."""
        if not self._auth:
            raise RuntimeError("SDK authentication not available for market data retrieval")

        await self._auth.ensure_initialized()

        # Use SDK to get simplified markets
        markets_data = self._auth.get_simplified_markets()
        markets = []

        for market_data in markets_data:
            market_info = self._parse_market_data(market_data)
            if market_info:
                markets.append(market_info)

        return markets

    def _parse_market_data(self, market_data: Dict[str, Any]) -> Optional[EventMarketInfo]:
        """Parse market data from API response into EventMarketInfo."""
        try:
            market_id = market_data.get("condition_id", "")
            question = market_data.get("question", "")

            # Parse outcomes
            outcomes = []
            for outcome_data in market_data.get("outcomes", []):
                outcome_info = OutcomeInfo(
                    outcome_id=outcome_data.get("token_id", ""),
                    outcome_name=outcome_data.get("name", ""),
                    current_price=Decimal(str(outcome_data.get("price", "0"))),
                    token_address=outcome_data.get("token_address", ""),
                    volume_24h=Decimal(str(outcome_data.get("volume_24h", "0"))),
                    liquidity=Decimal(str(outcome_data.get("liquidity", "0")))
                )
                outcomes.append(outcome_info)

            # Parse resolution status
            resolution_status = EventResolution.PENDING
            if market_data.get("closed", False):
                resolution_text = market_data.get("resolution", "").upper()
                if resolution_text in ["YES", "NO", "INVALID", "CANCELLED"]:
                    resolution_status = EventResolution[resolution_text]

            return EventMarketInfo(
                market_id=market_id,
                question=question,
                outcomes=outcomes,
                resolution_date=market_data.get("end_date_iso"),
                resolution_source=market_data.get("resolution_source", ""),
                tags=market_data.get("tags", []),
                volume_24h=Decimal(str(market_data.get("volume_24h", "0"))),
                liquidity=Decimal(str(market_data.get("liquidity", "0"))),
                status=resolution_status
            )

        except Exception as e:
            self.logger().error(f"Error parsing market data: {e}")
            return None

    def _parse_position_data(self, position_data: Dict[str, Any]) -> Optional[EventPosition]:
        """Parse position data from API response into EventPosition."""
        try:
            market_id = position_data.get("market_id", "")
            outcome_name = position_data.get("outcome", "YES")
            outcome = OutcomeType[outcome_name.upper()]

            return EventPosition(
                market_id=market_id,
                outcome=outcome,
                shares=Decimal(str(position_data.get("shares", "0"))),
                average_price=Decimal(str(position_data.get("average_price", "0"))),
                current_price=Decimal(str(position_data.get("current_price", "0"))),
                unrealized_pnl=Decimal(str(position_data.get("unrealized_pnl", "0"))),
                realized_pnl=Decimal(str(position_data.get("realized_pnl", "0"))),
                timestamp=position_data.get("timestamp", 0)
            )

        except Exception as e:
            self.logger().error(f"Error parsing position data: {e}")
            return None

    def _get_token_id(self, market_id: str, outcome: str) -> str:
        """Generate token ID for market and outcome.

        NOTE: This is a placeholder implementation. In production,
        token IDs should be fetched from Polymarket API or calculated
        using the official method.
        """
        outcome_index = "0" if outcome.upper() == "YES" else "1"
        hash_input = f"{market_id}_{outcome_index}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
