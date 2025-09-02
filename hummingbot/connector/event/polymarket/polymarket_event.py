"""
Polymarket Event connector implementing EventPyBase as specified in design document.
Uses canonical hyphen format trading pairs and event-specific order tracking.
"""

import time
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.event_py_base import EventPyBase
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import (
    EventMarketInfo,
    EventPosition,
    EventResolution,
    OrderType,
    OutcomeType,
    TradeType,
)
from hummingbot.core.data_type.event_in_flight_order import EventInFlightOrder
from hummingbot.core.data_type.event_pair import format_event_trading_pair, parse_event_trading_pair
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee

try:
    from py_clob_client.clob_types import MarketOrderArgs, OrderArgs
    from py_clob_client.order_builder.constants import BUY, SELL
    PY_CLOB_CLIENT_AVAILABLE = True
except ImportError:
    PY_CLOB_CLIENT_AVAILABLE = False
    OrderArgs = None
    MarketOrderArgs = None
    BUY = None
    SELL = None

from .polymarket_api_data_source import PolymarketAPIDataSource
from .polymarket_auth import PolymarketAuth
from .polymarket_constants import (
    DEFAULT_MAKER_FEE,
    DEFAULT_TAKER_FEE,
    MARKETS_URL,
    MAX_ACCEPTABLE_PRICE,
    MIN_ACCEPTABLE_PRICE,
    PRICE_CHANGE_THRESHOLD,
    QUOTE_ASSET,
    RATE_LIMIT_REQUESTS_PER_SECOND,
    SDK_ORDER_TYPE_MAPPING,
    SIGNATURE_TYPE_EOA,
    SIZE_CHANGE_THRESHOLD_PCT,
)


class PolymarketEvent(EventPyBase):
    """
    Polymarket Event CLOB connector using EventPyBase foundation.

    Implements prediction market trading with:
    - EIP-712 signature-based order placement
    - Event market resolution monitoring
    - Outcome-aware position tracking
    - Canonical hyphen format trading pairs (MARKET-OUTCOME-QUOTE)
    """

    def __init__(
        self,
        polymarket_private_key: str,
        polymarket_wallet_address: str,
        polymarket_signature_type: int = SIGNATURE_TYPE_EOA,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = False,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        domain: str = "polymarket"
    ):
        """
        Initialize Polymarket connector with improved SDK integration.

        Args:
            polymarket_private_key: Polygon private key for SDK authentication
            polymarket_wallet_address: Polygon wallet address
            polymarket_signature_type: EIP-712 signature type (0=EOA, 1=PROXY, 2=GNOSIS)
            trading_pairs: List of event trading pairs in MARKET-OUTCOME-QUOTE format
            trading_required: Whether trading functionality is required
            balance_asset_limit: Asset balance limits
            rate_limits_share_pct: Rate limit sharing percentage
            domain: Connector domain name
        """

        self._domain = domain
        self._trading_required = trading_required

        # Initialize trading pairs first (needed by parent constructors)
        self._trading_pairs = trading_pairs or []

        # Initialize SDK authentication with AuthBase wrapper
        self._auth = PolymarketAuth(
            private_key=polymarket_private_key,
            wallet_address=polymarket_wallet_address,
            signature_type=polymarket_signature_type
        )

        # Initialize API data source
        self._api_data_source = PolymarketAPIDataSource(self._trading_pairs, self._auth)

        # Call parent constructor
        super().__init__(self._trading_pairs, balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[PolymarketAuth]:
        return self._auth if self._trading_required else None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        """Rate limits for Polymarket API."""
        return [
            RateLimit(
                limit_id="ALL_ENDPOINTS",
                limit=RATE_LIMIT_REQUESTS_PER_SECOND,
                time_interval=1
            )
        ]

    @property
    def client_order_id_max_length(self) -> Optional[int]:
        return None

    @property
    def client_order_id_prefix(self) -> str:
        return "pm"

    @property
    def trading_pairs_request_path(self) -> str:
        return MARKETS_URL

    @property
    def trading_rules_request_path(self) -> str:
        return MARKETS_URL

    @property
    def check_network_request_path(self) -> str:
        return MARKETS_URL

    @property
    def resolution_poll_interval(self) -> int:
        """Interval for checking market resolutions."""
        return 300  # 5 minutes

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        """Order types supported by Polymarket."""
        return [
            OrderType.LIMIT,
            OrderType.LIMIT_MAKER,
            OrderType.IOC,
            OrderType.FOK,
            # Also support prediction aliases
            OrderType.PREDICTION_LIMIT,
            OrderType.PREDICTION_MARKET
        ]

    # === EventBase implementations ===

    async def get_active_markets(self) -> List[EventMarketInfo]:
        """Fetch active prediction markets from Polymarket API."""
        return await self._api_data_source.get_active_markets()

    async def get_market_info(self, market_id: str) -> Optional[EventMarketInfo]:
        """Get detailed information about a specific market."""
        return await self._api_data_source.get_market_info(market_id)

    async def place_prediction_order(
        self,
        market_id: str,
        outcome: OutcomeType,
        trade_type: TradeType,
        amount: Decimal,
        price: Decimal,
        **kwargs
    ) -> str:
        """Place order on prediction market using EIP-712 signatures."""

        # Generate client order ID
        order_id = self.generate_order_id()

        # Create trading pair in canonical format
        trading_pair = format_event_trading_pair(market_id, outcome, QUOTE_ASSET)

        # Validate order parameters
        if not self.validate_prediction_order(market_id, outcome, amount, price):
            raise ValueError(f"Invalid prediction order: {market_id}, {outcome}, {amount}, {price}")

        # Validate price range (from poly-maker best practices)
        if not self.validate_order_price(price):
            raise ValueError(f"Price {price} outside acceptable range ({MIN_ACCEPTABLE_PRICE}-{MAX_ACCEPTABLE_PRICE})")

        # Map order type
        order_type = kwargs.get("order_type", OrderType.LIMIT)
        if order_type in [OrderType.PREDICTION_LIMIT]:
            order_type = OrderType.LIMIT
        elif order_type in [OrderType.PREDICTION_MARKET]:
            order_type = OrderType.LIMIT  # Emulate as aggressive limit

        # Place order via API
        exchange_order_id = await self._place_event_order(
            market_id=market_id,
            outcome=outcome,
            trade_type=trade_type,
            amount=amount,
            price=price,
            order_type=order_type,
            **kwargs
        )

        # Start tracking with EventInFlightOrder
        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount,
            order_type=order_type,
            market_id=market_id,
            outcome=outcome,
            **kwargs
        )

        return order_id

    async def get_resolution_status(self, market_id: str) -> EventResolution:
        """Check resolution status of a market."""
        market_info = await self.get_market_info(market_id)
        if market_info:
            return market_info.status
        return EventResolution.PENDING

    async def claim_winnings(self, market_id: str) -> bool:
        """Claim winnings from resolved market."""
        try:
            # This would implement the redemption/claiming logic
            # For now, return success placeholder
            self.logger().info(f"Claiming winnings for market {market_id}")
            return True
        except Exception as e:
            self.logger().error(f"Error claiming winnings for {market_id}: {e}")
            return False

    # === EventPyBase implementations ===

    async def _get_current_positions(self) -> List[EventPosition]:
        """Get current positions from Polymarket API."""
        return await self._api_data_source.get_account_positions()

    async def _place_event_order(
        self,
        market_id: str,
        outcome: OutcomeType,
        trade_type: TradeType,
        amount: Decimal,
        price: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs
    ) -> str:
        """Place order via SDK only."""

        if not PY_CLOB_CLIENT_AVAILABLE:
            raise ImportError("py-clob-client is not installed. Run: pip install py-clob-client")

        await self._auth.ensure_initialized()

        # Get token ID for this outcome
        token_id = self._get_token_id(market_id, outcome.name)

        # Map trade type to SDK side
        side = BUY if trade_type == TradeType.BUY else SELL

        # Map order type
        sdk_order_type = self._map_order_type(order_type)

        if order_type in [OrderType.PREDICTION_MARKET]:
            # Use market order
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=float(amount * price) if trade_type == TradeType.BUY else float(amount),
                side=side,
                order_type=sdk_order_type
            )
            signed_order = self._auth.create_market_order(order_args)
        else:
            # Use limit order
            order_args = OrderArgs(
                token_id=token_id,
                price=float(price),
                size=float(amount),
                side=side
            )
            signed_order = self._auth.create_order(order_args)

        # Submit order
        response = self._auth.post_order(signed_order, sdk_order_type)

        exchange_order_id = response.get("id", "")
        if not exchange_order_id:
            raise ValueError("Failed to get exchange order ID from response")

        return exchange_order_id

    async def _cancel_event_order(self, client_order_id: str) -> bool:
        """Cancel order via SDK only."""
        await self._auth.ensure_initialized()

        tracked_order = self._order_tracker.fetch_order(client_order_id)
        if not tracked_order or not tracked_order.exchange_order_id:
            raise ValueError(f"Order {client_order_id} not found or missing exchange order ID")

        # Use SDK to cancel order
        return self._auth.cancel_order(tracked_order.exchange_order_id)

    def _map_order_type(self, order_type: OrderType) -> str:
        """Map HummingBot order type to SDK order types."""
        return SDK_ORDER_TYPE_MAPPING.get(order_type, "GTC")

    def start_tracking_order(
        self,
        order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        order_type: OrderType,
        market_id: str,
        outcome: OutcomeType,
        **kwargs
    ):
        """Start tracking order with EventInFlightOrder."""

        event_order = EventInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=self.current_timestamp,
            market_id=market_id,
            outcome=outcome,
            **kwargs
        )

        self._order_tracker.start_tracking_order(event_order)

    def generate_order_id(self) -> str:
        """Generate unique client order ID."""
        timestamp = int(time.time() * 1000)
        return f"pm_{timestamp}"

    def _get_token_id(self, market_id: str, outcome: str) -> str:
        """Get token ID using the same method as API data source."""
        return self._api_data_source._get_token_id(market_id, outcome)

    def validate_order_price(self, price: Decimal) -> bool:
        """Validate that price is within acceptable range."""
        return MIN_ACCEPTABLE_PRICE <= price <= MAX_ACCEPTABLE_PRICE

    def should_replace_order(
        self,
        existing_price: Decimal,
        new_price: Decimal,
        existing_size: Decimal,
        new_size: Decimal
    ) -> bool:
        """Check if order should be replaced based on material changes."""
        price_diff = abs(existing_price - new_price)
        size_diff = abs(existing_size - new_size)

        return (
            price_diff > PRICE_CHANGE_THRESHOLD or
            size_diff > new_size * SIZE_CHANGE_THRESHOLD_PCT
        )

    def cancel_orders_for_token(self, token_id: str) -> bool:
        """Cancel all orders for a specific token/asset."""
        try:
            return self._auth.cancel_market_orders(asset_id=token_id)
        except Exception as e:
            self.logger().error(f"Error canceling orders for token {token_id}: {e}")
            return False

    async def get_account_balances(self) -> Dict[str, Decimal]:
        """Get account balances from Polymarket."""
        return await self._api_data_source.get_account_balances()

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = Decimal("NaN"),
        is_maker: Optional[bool] = None
    ) -> AddedToCostTradeFee:
        """Calculate fees for Polymarket orders."""

        if is_maker is None:
            is_maker = order_type in [OrderType.LIMIT_MAKER]

        fee_rate = DEFAULT_MAKER_FEE if is_maker else DEFAULT_TAKER_FEE

        return AddedToCostTradeFee(
            percent=fee_rate
        )

    # === Required ExchangePyBase abstract methods ===

    @property
    def trading_pairs(self) -> List[str]:
        """Return list of supported trading pairs."""
        return self._trading_pairs

    async def _all_trade_updates_for_order(self, order: EventInFlightOrder) -> List:
        """Get all trade updates for a specific order."""
        # Event connectors handle this through SDK/API differently
        return []

    def _create_order_book_data_source(self):
        """Create order book data source."""
        return self._api_data_source

    def _create_user_stream_data_source(self):
        """Create user stream data source."""
        return self._api_data_source

    def _create_web_assistants_factory(self):
        """Create web assistants factory."""
        return None  # Event connectors use SDK directly

    async def _format_trading_rules(self, exchange_info: Dict) -> Dict:
        """Format trading rules from exchange info."""
        return {}

    async def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict):
        """Initialize trading pair symbols."""
        pass

    def _is_order_not_found_during_cancelation_error(self, err: Exception) -> bool:
        """Check if error indicates order not found during cancellation."""
        return "not found" in str(err).lower()

    def _is_order_not_found_during_status_update_error(self, err: Exception) -> bool:
        """Check if error indicates order not found during status update."""
        return "not found" in str(err).lower()

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """Check if exception is related to time synchronization."""
        return False

    async def _place_cancel(self, order_id: str, tracked_order: EventInFlightOrder) -> bool:
        """Cancel order implementation - delegates to existing event method."""
        return await self._cancel_event_order(order_id)

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs
    ) -> str:
        """Place order implementation - delegates to existing event method."""
        # Parse trading pair to get market_id and outcome
        market_id, outcome_str, quote = parse_event_trading_pair(trading_pair)
        outcome = OutcomeType.YES if outcome_str.upper() == "YES" else OutcomeType.NO

        # Delegate to existing event order placement
        exchange_order_id = await self._place_event_order(
            market_id=market_id,
            outcome=outcome,
            trade_type=trade_type,
            amount=amount,
            price=price,
            order_type=order_type,
            **kwargs
        )

        return exchange_order_id

    async def _request_order_status(self, tracked_order: EventInFlightOrder) -> Dict:
        """Request order status from exchange."""
        # Return basic status - event connectors handle this through API data source
        return {
            "id": tracked_order.exchange_order_id,
            "status": "unknown"
        }

    async def _update_balances(self):
        """Update account balances - delegates to existing method."""
        try:
            balances = await self.get_account_balances()
            for asset, balance in balances.items():
                self._account_balances[asset] = balance
        except Exception as e:
            self.logger().error(f"Failed to update balances: {e}")

    async def _update_trading_fees(self):
        """Update trading fees."""
        # Event connectors typically have fixed fees
        pass

    async def _user_stream_event_listener(self):
        """Listen to user stream events."""
        # Event connectors handle this through API data source
        pass

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        """Whether cancel requests are synchronous."""
        return True
