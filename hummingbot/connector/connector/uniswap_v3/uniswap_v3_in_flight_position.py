from decimal import Decimal
import asyncio
from async_timeout import timeout
from enum import Enum
from typing import (
    Dict,
    List,
    Any,
    Optional,
)

s_decimal_0 = Decimal("0")


class UniswapV3PositionStatus(Enum):
    PENDING_CREATE = 0  # add position request submitted but yet to get a returned hash nor token_id from Gateway
    OPEN = 1  # confirmed created in Uniswap, last_hash and token_id assigned
    PENDING_REMOVE = 2  # remove request submitted but yet to get a returned hash from Gateway
    REMOVED = 3  # confirmed removed
    REJECTED = 4
    FAILED = 5
    EXPIRED = 6

    def is_done(self):
        return self in (self.REMOVED, self.REJECTED, self.FAILED, self.EXPIRED)

    def is_pending(self):
        return self in (self.PENDING_CREATE, self.PENDING_REMOVE)

    def is_active(self):
        return self == self.OPEN


class UniswapV3InFlightPosition:
    def __init__(self,
                 hb_id: str,
                 token_id: Optional[str],
                 trading_pair: str,
                 upper_price: Decimal,
                 lower_price: Decimal,
                 base_amount: Decimal,
                 quote_amount: Decimal,
                 fee_tier: str,
                 gas_price: Decimal = Decimal("0"),
                 tx_fees: List = [],
                 last_status: UniswapV3PositionStatus = UniswapV3PositionStatus.PENDING_CREATE,
                 last_tx_hash: Optional[str] = None):
        self.hb_id = hb_id
        self.token_id = token_id
        self.trading_pair = trading_pair
        self.upper_price = upper_price
        self.lower_price = lower_price
        self.base_amount = base_amount
        self.quote_amount = quote_amount
        self.gas_price = gas_price
        self.tx_fees = tx_fees
        self.fee_tier = fee_tier
        self.last_status = last_status
        self.last_tx_hash = last_tx_hash
        self.last_tx_hash_update_event = asyncio.Event()
        self.current_base_amount = s_decimal_0
        self.current_quote_amount = s_decimal_0
        self.unclaimed_base_amount = s_decimal_0
        self.unclaimed_quote_amount = s_decimal_0

    def update_last_tx_hash(self, last_tx_hash: Optional[str]):
        self.last_tx_hash = last_tx_hash
        if last_tx_hash is not None:
            self.last_tx_hash_update_event.set()
        else:
            self.last_tx_hash_update_event = asyncio.Event()

    async def get_last_tx_hash(self):
        if self.last_tx_hash is None:
            async with timeout(100):
                await self.last_tx_hash_update_event.wait()
        return self.last_tx_hash

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "UniswapV3InFlightPosition":
        return UniswapV3InFlightPosition(
            hb_id=data["hb_id"],
            token_id=data["token_id"],
            trading_pair=data["trading_pair"],
            last_status=getattr(UniswapV3PositionStatus, data["last_status"]),
            upper_price=Decimal(data["upper_price"]),
            lower_price=Decimal(data["lower_price"]),
            base_amount=Decimal(data["base_amount"]),
            quote_amount=Decimal(data["quote_amount"]),
            gas_price=Decimal(data["gas_price"]),
            tx_fees=[Decimal(fee) for fee in data["tx_fees"]],
            fee_tier=data["fee_tier"],
            last_tx_hash=data["last_tx_hash"],
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "hb_id": self.hb_id,
            "token_id": self.token_id,
            "trading_pair": self.trading_pair,
            "last_status": self.last_status.name,
            "upper_price": str(self.upper_price),
            "lower_price": str(self.lower_price),
            "base_amount": str(self.base_amount),
            "quote_amount": str(self.quote_amount),
            "gas_price": str(self.gas_price),
            "tx_fees": [str(fee) for fee in self.tx_fees],
            "fee_tier": str(self.fee_tier),
            "last_tx_hash": self.last_tx_hash
        }
