from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from hummingbot.core.data_type.common import TradeType


class InitialPositionConfig(BaseModel):
    """
    Configuration for an initial position that the controller should consider.
    This is used when the user already has assets in their account and wants
    the controller to manage them.
    """
    connector_name: str
    trading_pair: str
    amount: Decimal
    side: TradeType

    @field_validator('side', mode='before')
    @classmethod
    def parse_side(cls, v):
        """Parse side field from string to TradeType enum."""
        if isinstance(v, str):
            try:
                return TradeType[v.upper()]
            except KeyError:
                # If direct enum name lookup fails, try numeric value
                try:
                    return TradeType(int(v))
                except (ValueError, KeyError):
                    raise ValueError(f"Invalid side value: {v}. Expected 'BUY' or 'SELL'")
        return v

    model_config = ConfigDict(arbitrary_types_allowed=True)
