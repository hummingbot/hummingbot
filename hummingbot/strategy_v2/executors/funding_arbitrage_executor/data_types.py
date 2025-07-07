from decimal import Decimal
from typing import Literal, Optional

from pydantic import Field, field_validator

from hummingbot.strategy_v2.executors.data_types import ConnectorPair, ExecutorConfigBase


class FundingArbitrageExecutorConfig(ExecutorConfigBase):
    """
    Configuration for the Funding Arbitrage Executor.

    This executor manages a pair of opposing positions (long and short) on two
    different exchanges to capture funding rate differentials while using
    limit order management for optimal execution.
    """
    type: Literal["funding_arbitrage_executor"] = "funding_arbitrage_executor"

    # Market configuration
    long_market: ConnectorPair = Field(
        ...,
        description="The market where the long position will be opened"
    )

    short_market: ConnectorPair = Field(
        ...,
        description="The market where the short position will be opened"
    )

    # Position sizing
    position_size_quote: Decimal = Field(
        ...,
        gt=0,
        description="The position size in quote asset for each leg of the arbitrage"
    )

    leverage: int = Field(
        default=20,
        ge=1,
        description="Leverage to use for both positions"
    )

    # Risk management parameters
    take_profit_pct: Optional[Decimal] = Field(
        default=Decimal("0.01"),
        ge=0,
        description="Take profit threshold as percentage of position size (e.g., 0.01 for 1%)"
    )

    stop_loss_pct: Optional[Decimal] = Field(
        default=Decimal("0.02"),
        ge=0,
        description="Stop loss threshold as percentage of position size (e.g., 0.02 for 2%)"
    )

    max_position_duration_seconds: Optional[int] = Field(
        default=24 * 60 * 60,  # 24 hours
        gt=0,
        description="Maximum duration to hold the position in seconds"
    )

    # Order management parameters
    entry_limit_order_spread_bps: int = Field(
        default=2,
        ge=0,
        description="Spread in basis points from best bid/ask for entry limit orders"
    )

    # Asymmetric fill handling
    asymmetric_fill_timeout_seconds: int = Field(
        default=300,  # 5 minutes
        ge=1,
        description="Timeout in seconds before closing positions if only one side is filled"
    )

    # Order renewal parameters
    order_renewal_threshold_pct: Decimal = Field(
        default=Decimal("0.005"),  # 0.5%
        ge=0,
        description="Price movement threshold to trigger order renewal (e.g., 0.005 for 0.5%)"
    )

    # Funding arbitrage specific
    min_funding_rate_differential: Decimal = Field(
        default=Decimal("0.001"),
        gt=-0.005,
        description="Minimum funding rate differential required to maintain the position"
    )

    @field_validator("take_profit_pct", "stop_loss_pct", "order_renewal_threshold_pct", mode="before")
    @classmethod
    def validate_percentages(cls, v):
        """Ensure percentage values are reasonable."""
        if v is not None:
            # Convert to Decimal if it's a string or other numeric type
            try:
                decimal_v = Decimal(str(v)) if not isinstance(v, Decimal) else v
                if decimal_v > 1:
                    raise ValueError("Percentage values should be decimals (e.g., 0.01 for 1%), not whole numbers")
                return decimal_v
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid percentage value: {v}. Must be a valid number.") from e
        return v

    @field_validator("entry_limit_order_spread_bps")
    @classmethod
    def validate_spread_bps(cls, v):
        """Validate spread basis points."""
        if v > 1000:  # 10%
            raise ValueError("Spread basis points should be reasonable (max 1000 bps = 10%)")
        return v

    @field_validator("leverage")
    @classmethod
    def validate_leverage(cls, v):
        """Validate leverage value."""
        if v > 100:
            raise ValueError("Leverage should be reasonable (max 100x)")
        return v

    def validate_markets(self) -> bool:
        """
        Validate that the long and short markets are compatible for arbitrage.
        They should have the same base asset but can have different quote assets.
        """
        long_base = self.long_market.trading_pair.split("-")[0]
        short_base = self.short_market.trading_pair.split("-")[0]

        if long_base != short_base:
            raise ValueError(f"Base assets must match: {long_base} != {short_base}")

        if self.long_market.connector_name == self.short_market.connector_name:
            raise ValueError("Long and short markets must be on different exchanges")

        return True

    @property
    def base_asset(self) -> str:
        """Get the base asset from the trading pair."""
        return self.long_market.trading_pair.split("-")[0]

    @property
    def long_quote_asset(self) -> str:
        """Get the quote asset for the long market."""
        return self.long_market.trading_pair.split("-")[1]

    @property
    def short_quote_asset(self) -> str:
        """Get the quote asset for the short market."""
        return self.short_market.trading_pair.split("-")[1]

    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate_markets()
