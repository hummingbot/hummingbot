from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.core.data_type.common import OrderType, OutcomeType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class EventInFlightOrder(InFlightOrder):
    """
    InFlightOrder extension for event/prediction market orders.

    This class adds event-specific fields:
    - outcome: YES/NO outcome being traded
    - market_id: Event market identifier
    - shares: Number of shares (instead of generic amount)
    - price: Price per share (0-1 range for prediction markets)
    """

    def __init__(
        self,
        client_order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        order_type: OrderType,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        creation_timestamp: float,
        market_id: str,
        outcome: OutcomeType,
        initial_state: OrderState = OrderState.PENDING_CREATE,
        leverage: int = 1,
        **kwargs
    ):
        """
        Initialize an EventInFlightOrder.

        Args:
            client_order_id: Client-generated order ID
            exchange_order_id: Exchange-assigned order ID (can be None initially)
            trading_pair: Trading pair in format "MARKET_ID-OUTCOME-QUOTE"
            order_type: Type of order (PREDICTION_LIMIT, PREDICTION_MARKET, etc.)
            trade_type: BUY or SELL
            price: Price per share (0-1 range)
            amount: Number of shares to trade
            creation_timestamp: Order creation time
            market_id: Event market identifier
            outcome: YES or NO outcome
            initial_state: Initial order state (OrderState enum)
            leverage: Leverage (usually 1 for prediction markets)
            **kwargs: Additional exchange-specific parameters
        """
        super().__init__(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=creation_timestamp,
            initial_state=initial_state,
            leverage=leverage,
        )

        self.market_id = market_id
        self.outcome = outcome

        # Store additional event-specific parameters
        self._event_params = kwargs

        # Validate price range for prediction markets
        self._validate_prediction_price()

    @property
    def shares(self) -> Decimal:
        """
        Number of shares being traded (alias for amount).

        Returns:
            Number of shares as Decimal
        """
        return self.amount

    @property
    def price_per_share(self) -> Decimal:
        """
        Price per share (alias for price).

        Returns:
            Price per share as Decimal (0-1 range)
        """
        return self.price

    def _validate_prediction_price(self):
        """
        Validate that price is in valid range for prediction markets (0-1).

        Raises:
            ValueError: If price is outside valid range
        """
        if self.price < Decimal("0") or self.price > Decimal("1"):
            raise ValueError(f"Prediction market price must be between 0 and 1, got {self.price}")

    def to_json(self) -> Dict[str, Any]:
        """
        Convert order to JSON representation, including event-specific fields.

        Returns:
            Dictionary representation of the order
        """
        base_json = super().to_json()

        # Add event-specific fields
        base_json.update({
            "market_id": self.market_id,
            "outcome": self.outcome.name,
            "shares": str(self.shares),
            "price_per_share": str(self.price_per_share),
        })

        # Add any additional event parameters
        if self._event_params:
            base_json["event_params"] = self._event_params

        return base_json

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "EventInFlightOrder":
        """
        Create EventInFlightOrder from JSON representation.

        Args:
            data: Dictionary containing order data

        Returns:
            EventInFlightOrder instance
        """
        # Extract event-specific fields
        market_id = data.get("market_id", "")
        outcome_name = data.get("outcome", "YES")
        outcome = OutcomeType[outcome_name]

        # Extract additional event parameters
        event_params = data.get("event_params", {})

        return cls(
            client_order_id=data["client_order_id"],
            exchange_order_id=data.get("exchange_order_id"),
            trading_pair=data["trading_pair"],
            order_type=OrderType(data["order_type"]),
            trade_type=TradeType(data["trade_type"]),
            price=Decimal(str(data["price"])),
            amount=Decimal(str(data["amount"])),
            creation_timestamp=float(data["creation_timestamp"]),
            market_id=market_id,
            outcome=outcome,
            initial_state=OrderState[data.get("last_state", "PENDING_CREATE")],
            leverage=int(data.get("leverage", 1)),
            **event_params
        )

    def update_exchange_order_id(self, exchange_order_id: str):
        """
        Update the exchange order ID when it becomes available.

        Args:
            exchange_order_id: Exchange-assigned order ID
        """
        self.exchange_order_id = exchange_order_id

    def is_prediction_order(self) -> bool:
        """
        Check if this is a prediction market order.

        Returns:
            Always True for EventInFlightOrder
        """
        return True

    def get_outcome_symbol(self) -> str:
        """
        Get the outcome symbol for display purposes.

        Returns:
            Outcome name ("YES" or "NO")
        """
        return self.outcome.name

    def calculate_total_cost(self, include_fees: bool = False, fee_rate: Decimal = Decimal("0")) -> Decimal:
        """
        Calculate total cost of the order.

        Args:
            include_fees: Whether to include fees in calculation
            fee_rate: Fee rate as decimal (e.g., 0.02 for 2%)

        Returns:
            Total cost as Decimal
        """
        base_cost = self.shares * self.price_per_share

        if include_fees:
            fees = base_cost * fee_rate
            return base_cost + fees

        return base_cost

    def __str__(self) -> str:
        """
        String representation of the order.

        Returns:
            Human-readable order description
        """
        return (
            f"EventOrder(id={self.client_order_id}, "
            f"market={self.market_id}, "
            f"outcome={self.outcome.name}, "
            f"type={self.trade_type.name}, "
            f"shares={self.shares}, "
            f"price={self.price_per_share}, "
            f"state={self.last_state})"
        )

    def __repr__(self) -> str:
        """
        Detailed representation of the order.

        Returns:
            Detailed order representation
        """
        return (
            f"EventInFlightOrder("
            f"client_order_id='{self.client_order_id}', "
            f"exchange_order_id='{self.exchange_order_id}', "
            f"trading_pair='{self.trading_pair}', "
            f"market_id='{self.market_id}', "
            f"outcome={self.outcome}, "
            f"order_type={self.order_type}, "
            f"trade_type={self.trade_type}, "
            f"shares={self.shares}, "
            f"price_per_share={self.price_per_share}, "
            f"state='{self.last_state}', "
            f"timestamp={self.creation_timestamp})"
        )
