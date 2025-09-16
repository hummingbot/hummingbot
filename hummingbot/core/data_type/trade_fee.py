"""
Trade fee data types for Hummingbot framework.
Minimal implementation to support connector development.
"""

from decimal import Decimal
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


@dataclass
class TokenAmount:
    """
    Represents an amount of a specific token/asset.
    """
    token: str
    amount: Decimal

    def __post_init__(self):
        """Post-initialization validation."""
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))

    def __str__(self) -> str:
        """String representation."""
        return f"{self.amount} {self.token}"

    def __add__(self, other: 'TokenAmount') -> 'TokenAmount':
        """Add two TokenAmount objects."""
        if self.token != other.token:
            raise ValueError(f"Cannot add different tokens: {self.token} and {other.token}")
        return TokenAmount(self.token, self.amount + other.amount)

    def __sub__(self, other: 'TokenAmount') -> 'TokenAmount':
        """Subtract two TokenAmount objects."""
        if self.token != other.token:
            raise ValueError(f"Cannot subtract different tokens: {self.token} and {other.token}")
        return TokenAmount(self.token, self.amount - other.amount)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'token': self.token,
            'amount': str(self.amount)
        }


class TradeFeeType(Enum):
    """Types of trade fees."""
    FLAT_FEE = "FLAT_FEE"
    PERCENTAGE_FEE = "PERCENTAGE_FEE"


class TradeFeePaymentMethod(Enum):
    """Methods of paying trade fees."""
    BASE_CURRENCY = "BASE_CURRENCY"
    QUOTE_CURRENCY = "QUOTE_CURRENCY"
    THIRD_PARTY_TOKEN = "THIRD_PARTY_TOKEN"


@dataclass
class TradeFeeSchema:
    """
    Schema for trade fee structure.
    """
    maker_percent_fee_decimal: Decimal
    taker_percent_fee_decimal: Decimal
    maker_fixed_fees: Optional[List[Dict[str, Any]]] = None
    taker_fixed_fees: Optional[List[Dict[str, Any]]] = None
    buy_percent_fee_deducted_from_returns: bool = False
    
    def __post_init__(self):
        """Post-initialization validation."""
        # Ensure fee decimals are Decimal objects
        if not isinstance(self.maker_percent_fee_decimal, Decimal):
            self.maker_percent_fee_decimal = Decimal(str(self.maker_percent_fee_decimal))
        
        if not isinstance(self.taker_percent_fee_decimal, Decimal):
            self.taker_percent_fee_decimal = Decimal(str(self.taker_percent_fee_decimal))


class TradeFeeBase:
    """
    Base class for trade fees.
    """

    def __init__(self, fee_asset: str, fee_amount: Decimal):
        """
        Initialize trade fee base.

        Args:
            fee_asset: Asset used to pay the fee
            fee_amount: Fee amount
        """
        self.fee_asset = fee_asset
        self.fee_amount = Decimal(str(fee_amount)) if not isinstance(fee_amount, Decimal) else fee_amount

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'fee_asset': self.fee_asset,
            'fee_amount': str(self.fee_amount)
        }


@dataclass
class TradeFee(TradeFeeBase):
    """
    Represents a trade fee for a specific transaction.
    """
    fee_asset: str
    fee_amount: Decimal
    fee_type: TradeFeeType = TradeFeeType.PERCENTAGE_FEE
    payment_method: TradeFeePaymentMethod = TradeFeePaymentMethod.QUOTE_CURRENCY
    
    def __post_init__(self):
        """Post-initialization validation."""
        # Initialize base class
        TradeFeeBase.__init__(self, self.fee_asset, self.fee_amount)
        # Ensure fee amount is a Decimal object
        if not isinstance(self.fee_amount, Decimal):
            self.fee_amount = Decimal(str(self.fee_amount))
    
    @classmethod
    def from_percentage(cls, 
                       fee_asset: str, 
                       fee_percentage: Decimal, 
                       trade_amount: Decimal) -> 'TradeFee':
        """
        Create a TradeFee from a percentage.
        
        Args:
            fee_asset: Asset used to pay the fee
            fee_percentage: Fee percentage (e.g., 0.001 for 0.1%)
            trade_amount: Amount being traded
            
        Returns:
            TradeFee instance
        """
        fee_amount = trade_amount * fee_percentage
        return cls(
            fee_asset=fee_asset,
            fee_amount=fee_amount,
            fee_type=TradeFeeType.PERCENTAGE_FEE
        )
    
    @classmethod
    def from_flat_fee(cls, 
                     fee_asset: str, 
                     fee_amount: Decimal) -> 'TradeFee':
        """
        Create a TradeFee from a flat fee amount.
        
        Args:
            fee_asset: Asset used to pay the fee
            fee_amount: Flat fee amount
            
        Returns:
            TradeFee instance
        """
        return cls(
            fee_asset=fee_asset,
            fee_amount=fee_amount,
            fee_type=TradeFeeType.FLAT_FEE
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trade fee to dictionary representation.
        
        Returns:
            Dictionary representation of the trade fee
        """
        return {
            'fee_asset': self.fee_asset,
            'fee_amount': str(self.fee_amount),
            'fee_type': self.fee_type.value,
            'payment_method': self.payment_method.value
        }
    
    def __str__(self) -> str:
        """String representation of the trade fee."""
        return f"TradeFee({self.fee_amount} {self.fee_asset}, {self.fee_type.value})"


class TradeFeeCalculator:
    """
    Calculator for trade fees based on trading rules and exchange settings.
    """
    
    def __init__(self, fee_schema: TradeFeeSchema):
        """
        Initialize the fee calculator.
        
        Args:
            fee_schema: Fee schema for the exchange
        """
        self.fee_schema = fee_schema
    
    def calculate_maker_fee(self, 
                           trading_pair: str, 
                           trade_amount: Decimal, 
                           price: Decimal,
                           is_buy: bool) -> TradeFee:
        """
        Calculate maker fee for a trade.
        
        Args:
            trading_pair: Trading pair
            trade_amount: Amount being traded
            price: Trade price
            is_buy: Whether this is a buy order
            
        Returns:
            TradeFee instance
        """
        base_asset, quote_asset = trading_pair.split("-")
        
        if is_buy:
            # For buy orders, fee is typically paid in base asset
            fee_asset = base_asset
            fee_amount = trade_amount * self.fee_schema.maker_percent_fee_decimal
        else:
            # For sell orders, fee is typically paid in quote asset
            fee_asset = quote_asset
            quote_amount = trade_amount * price
            fee_amount = quote_amount * self.fee_schema.maker_percent_fee_decimal
        
        return TradeFee(
            fee_asset=fee_asset,
            fee_amount=fee_amount,
            fee_type=TradeFeeType.PERCENTAGE_FEE,
            payment_method=TradeFeePaymentMethod.BASE_CURRENCY if is_buy else TradeFeePaymentMethod.QUOTE_CURRENCY
        )
    
    def calculate_taker_fee(self, 
                           trading_pair: str, 
                           trade_amount: Decimal, 
                           price: Decimal,
                           is_buy: bool) -> TradeFee:
        """
        Calculate taker fee for a trade.
        
        Args:
            trading_pair: Trading pair
            trade_amount: Amount being traded
            price: Trade price
            is_buy: Whether this is a buy order
            
        Returns:
            TradeFee instance
        """
        base_asset, quote_asset = trading_pair.split("-")
        
        if is_buy:
            # For buy orders, fee is typically paid in base asset
            fee_asset = base_asset
            fee_amount = trade_amount * self.fee_schema.taker_percent_fee_decimal
        else:
            # For sell orders, fee is typically paid in quote asset
            fee_asset = quote_asset
            quote_amount = trade_amount * price
            fee_amount = quote_amount * self.fee_schema.taker_percent_fee_decimal
        
        return TradeFee(
            fee_asset=fee_asset,
            fee_amount=fee_amount,
            fee_type=TradeFeeType.PERCENTAGE_FEE,
            payment_method=TradeFeePaymentMethod.BASE_CURRENCY if is_buy else TradeFeePaymentMethod.QUOTE_CURRENCY
        )


@dataclass
class DeductedFromReturnsTradeFee(TradeFee):
    """
    Trade fee that is deducted from returns.
    Used when the fee is taken from the received amount rather than added on top.
    """

    def __post_init__(self):
        """Post-initialization for deducted fee."""
        super().__post_init__()
        self.payment_method = TradeFeePaymentMethod.BASE_CURRENCY

    @classmethod
    def from_trade_fee(cls, trade_fee: TradeFee) -> 'DeductedFromReturnsTradeFee':
        """
        Create a DeductedFromReturnsTradeFee from a regular TradeFee.

        Args:
            trade_fee: Regular trade fee to convert

        Returns:
            DeductedFromReturnsTradeFee instance
        """
        return cls(
            fee_asset=trade_fee.fee_asset,
            fee_amount=trade_fee.fee_amount,
            fee_type=trade_fee.fee_type,
            payment_method=TradeFeePaymentMethod.BASE_CURRENCY
        )


# Default fee schemas for common exchanges
DEFAULT_FEE_SCHEMA = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),  # 0.1%
    taker_percent_fee_decimal=Decimal("0.001"),  # 0.1%
    buy_percent_fee_deducted_from_returns=False
)

ZERO_FEE_SCHEMA = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
    buy_percent_fee_deducted_from_returns=False
)
