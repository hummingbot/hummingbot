from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.common import EventMarketInfo, EventPosition, EventResolution, OutcomeType, TradeType

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class EventBase(ExchangeBase, ABC):
    """
    EventBase provides extra functionality in addition to ExchangeBase for event/prediction market exchanges.

    This base class handles:
    - Event market management and resolution tracking
    - Outcome-specific positions (YES/NO)
    - Market resolution monitoring and winnings claiming
    - Event-specific order validation
    """

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__(client_config_map)
        self._event_markets: Dict[str, EventMarketInfo] = {}
        self._event_positions: Dict[str, EventPosition] = {}
        self._resolution_status: Dict[str, EventResolution] = {}

    @abstractmethod
    def get_active_markets(self) -> List[EventMarketInfo]:
        """
        Retrieve all active event/prediction markets available for trading.

        Returns:
            List of EventMarketInfo objects containing market details
        """
        raise NotImplementedError

    @abstractmethod
    def get_market_info(self, market_id: str) -> Optional[EventMarketInfo]:
        """
        Get detailed information about a specific event market.

        Args:
            market_id: Unique identifier for the event market

        Returns:
            EventMarketInfo object or None if market not found
        """
        raise NotImplementedError

    @abstractmethod
    def place_prediction_order(
        self,
        market_id: str,
        outcome: OutcomeType,
        trade_type: TradeType,
        amount: Decimal,
        price: Decimal,
        **kwargs
    ) -> str:
        """
        Place an order on a prediction market for a specific outcome.

        Args:
            market_id: The event market identifier
            outcome: YES or NO outcome
            trade_type: BUY or SELL
            amount: Number of shares to trade
            price: Price per share (0-1 range)
            **kwargs: Additional exchange-specific parameters

        Returns:
            Order ID string
        """
        raise NotImplementedError

    @abstractmethod
    def get_resolution_status(self, market_id: str) -> EventResolution:
        """
        Check the current resolution status of an event market.

        Args:
            market_id: The event market identifier

        Returns:
            EventResolution enum (PENDING, YES, NO, INVALID, CANCELLED)
        """
        raise NotImplementedError

    @abstractmethod
    def claim_winnings(self, market_id: str) -> bool:
        """
        Claim winnings from a resolved event market.

        Args:
            market_id: The resolved event market identifier

        Returns:
            True if claiming was successful or attempted, False otherwise
        """
        raise NotImplementedError

    def get_event_markets(self) -> Dict[str, EventMarketInfo]:
        """
        Get all cached event markets.

        Returns:
            Dictionary of market_id -> EventMarketInfo
        """
        return self._event_markets.copy()

    def get_event_positions(self) -> Dict[str, EventPosition]:
        """
        Get all current event market positions.

        Returns:
            Dictionary of position_id -> EventPosition
        """
        return self._event_positions.copy()

    def update_market_info(self, market_info: EventMarketInfo):
        """
        Update cached market information.

        Args:
            market_info: Updated EventMarketInfo object
        """
        self._event_markets[market_info.market_id] = market_info

    def update_position(self, position: EventPosition):
        """
        Update position information.

        Args:
            position: Updated EventPosition object
        """
        position_key = f"{position.market_id}_{position.outcome.name}"
        self._event_positions[position_key] = position

    def is_market_resolved(self, market_id: str) -> bool:
        """
        Check if a market has been resolved.

        Args:
            market_id: The event market identifier

        Returns:
            True if market is resolved, False otherwise
        """
        status = self._resolution_status.get(market_id, EventResolution.PENDING)
        return status in [EventResolution.YES, EventResolution.NO, EventResolution.INVALID, EventResolution.CANCELLED]

    def validate_prediction_order(
        self,
        market_id: str,
        outcome: OutcomeType,
        amount: Decimal,
        price: Decimal
    ) -> bool:
        """
        Validate a prediction market order before placement.

        Args:
            market_id: The event market identifier
            outcome: YES or NO outcome
            amount: Number of shares
            price: Price per share (should be 0-1)

        Returns:
            True if order is valid, False otherwise
        """
        # Check if market exists and is active
        market = self._event_markets.get(market_id)
        if market is None:
            self.logger().error(f"Market {market_id} not found")
            return False

        if market.status != EventResolution.PENDING:
            self.logger().error(f"Market {market_id} is not active (status: {market.status})")
            return False

        # Validate price range (0-1 for prediction markets)
        if price < Decimal("0") or price > Decimal("1"):
            self.logger().error(f"Price {price} is out of valid range (0-1)")
            return False

        # Validate amount is positive
        if amount <= Decimal("0"):
            self.logger().error(f"Amount {amount} must be positive")
            return False

        return True

    def get_market_by_trading_pair(self, trading_pair: str) -> Optional[EventMarketInfo]:
        """
        Get market info from trading pair format: MARKET_ID-OUTCOME-QUOTE

        Args:
            trading_pair: Trading pair in format like "ELECTION2024-YES-USDC"

        Returns:
            EventMarketInfo object or None
        """
        try:
            parts = trading_pair.split("-")
            if len(parts) >= 2:
                # Extract market_id (everything except last two parts which are outcome and quote)
                market_id = "-".join(parts[:-2])
                return self._event_markets.get(market_id)
        except Exception as e:
            self.logger().error(f"Failed to parse trading pair {trading_pair}: {e}")

        return None

    def parse_trading_pair(self, trading_pair: str) -> tuple[str, OutcomeType, str]:
        """
        Parse trading pair into components: market_id, outcome, quote_asset

        Args:
            trading_pair: Trading pair in format like "ELECTION2024-YES-USDC"

        Returns:
            Tuple of (market_id, outcome, quote_asset)
        """
        parts = trading_pair.split("-")
        if len(parts) < 3:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        quote_asset = parts[-1]
        outcome_str = parts[-2]
        market_id = "-".join(parts[:-2])

        try:
            outcome = OutcomeType[outcome_str.upper()]
        except KeyError:
            raise ValueError(f"Invalid outcome: {outcome_str}")

        return market_id, outcome, quote_asset
