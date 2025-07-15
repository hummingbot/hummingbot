"""
Type definitions for Gateway connectors.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class TradingType(str, Enum):
    """Supported trading types."""
    ROUTER = "router"
    AMM = "amm"
    CLMM = "clmm"


class TransactionStatus(int, Enum):
    """Transaction status codes."""
    PENDING = 0
    CONFIRMED = 1
    FAILED = -1


@dataclass
class TokenInfo:
    """Token information."""
    symbol: str
    address: str
    decimals: int
    name: Optional[str] = None
    chain: Optional[str] = None
    network: Optional[str] = None


@dataclass
class PriceQuote:
    """Price quote for a swap."""
    price: Decimal
    amount_in: Decimal
    amount_out: Decimal
    min_amount_out: Optional[Decimal] = None
    max_amount_in: Optional[Decimal] = None
    gas_estimate: Optional[Decimal] = None
    gas_price: Optional[Decimal] = None
    compute_units: Optional[int] = None
    pool_address: Optional[str] = None
    route: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceQuote":
        """Create PriceQuote from dictionary."""
        return cls(
            price=Decimal(str(data.get("price", 0))),
            amount_in=Decimal(str(data.get("estimatedAmountIn", 0))),
            amount_out=Decimal(str(data.get("estimatedAmountOut", 0))),
            min_amount_out=Decimal(str(data.get("minAmountOut", 0))) if "minAmountOut" in data else None,
            max_amount_in=Decimal(str(data.get("maxAmountIn", 0))) if "maxAmountIn" in data else None,
            gas_estimate=Decimal(str(data.get("gasEstimate", 0))) if "gasEstimate" in data else None,
            gas_price=Decimal(str(data.get("gasPrice", 0))) if "gasPrice" in data else None,
            compute_units=data.get("computeUnits"),
            pool_address=data.get("poolAddress"),
            route=data.get("route")
        )


@dataclass
class PoolInfo:
    """Pool information for AMM/CLMM."""
    pool_address: str
    base_token: str
    quote_token: str
    fee_tier: Optional[Decimal] = None
    liquidity: Optional[Decimal] = None
    sqrt_price: Optional[Decimal] = None
    current_tick: Optional[int] = None
    base_reserve: Optional[Decimal] = None
    quote_reserve: Optional[Decimal] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PoolInfo":
        """Create PoolInfo from dictionary."""
        return cls(
            pool_address=data["poolAddress"],
            base_token=data.get("baseToken", data.get("token0", "")),
            quote_token=data.get("quoteToken", data.get("token1", "")),
            fee_tier=Decimal(str(data["feeTier"])) if "feeTier" in data else None,
            liquidity=Decimal(str(data["liquidity"])) if "liquidity" in data else None,
            sqrt_price=Decimal(str(data["sqrtPrice"])) if "sqrtPrice" in data else None,
            current_tick=data.get("currentTick"),
            base_reserve=Decimal(str(data["baseReserve"])) if "baseReserve" in data else None,
            quote_reserve=Decimal(str(data["quoteReserve"])) if "quoteReserve" in data else None
        )


@dataclass
class Position:
    """Liquidity position for AMM/CLMM."""
    position_id: str
    pool_address: str
    base_token: str
    quote_token: str
    base_amount: Decimal
    quote_amount: Decimal
    liquidity: Optional[Decimal] = None
    fee_tier: Optional[Decimal] = None
    tick_lower: Optional[int] = None
    tick_upper: Optional[int] = None
    unclaimed_fees: Optional[Dict[str, Decimal]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create Position from dictionary."""
        unclaimed_fees = None
        if "unclaimedFees" in data:
            unclaimed_fees = {
                "base": Decimal(str(data["unclaimedFees"].get("token0", 0))),
                "quote": Decimal(str(data["unclaimedFees"].get("token1", 0)))
            }

        return cls(
            position_id=str(data.get("positionId", data.get("id", ""))),
            pool_address=data["poolAddress"],
            base_token=data.get("baseToken", data.get("token0", "")),
            quote_token=data.get("quoteToken", data.get("token1", "")),
            base_amount=Decimal(str(data.get("baseAmount", data.get("amount0", 0)))),
            quote_amount=Decimal(str(data.get("quoteAmount", data.get("amount1", 0)))),
            liquidity=Decimal(str(data["liquidity"])) if "liquidity" in data else None,
            fee_tier=Decimal(str(data["feeTier"])) if "feeTier" in data else None,
            tick_lower=data.get("tickLower"),
            tick_upper=data.get("tickUpper"),
            unclaimed_fees=unclaimed_fees
        )


@dataclass
class TransactionResult:
    """Result of a transaction execution."""
    tx_hash: str
    status: TransactionStatus
    order_id: Optional[str] = None
    gas_used: Optional[int] = None
    gas_price: Optional[Decimal] = None
    compute_units_used: Optional[int] = None
    error: Optional[str] = None
    timestamp: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionResult":
        """Create TransactionResult from dictionary."""
        status = TransactionStatus.PENDING
        if data.get("confirmed"):
            status = TransactionStatus.CONFIRMED
        elif data.get("failed"):
            status = TransactionStatus.FAILED

        return cls(
            tx_hash=data.get("signature", data.get("txHash", "")),
            status=status,
            order_id=data.get("orderId"),
            gas_used=data.get("gasUsed"),
            gas_price=Decimal(str(data["gasPrice"])) if "gasPrice" in data else None,
            compute_units_used=data.get("computeUnitsUsed"),
            error=data.get("error"),
            timestamp=data.get("timestamp")
        )
