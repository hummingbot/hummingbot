import hashlib
import random
import time
from decimal import Decimal

import base58
from pydantic.v1 import BaseModel, validator

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.data_type.common import TradeType


class ExecutorConfigBase(BaseModel):
    id: str = None  # Make ID optional
    type: str
    timestamp: float
    controller_id: str = "main"

    @validator('id', pre=True, always=True)
    def set_id(cls, v, values):
        if v is None:
            # Use timestamp from values if available, else current time
            timestamp = values.get('timestamp', time.time())
            unique_component = random.randint(0, 99999)
            raw_id = f"{timestamp}-{unique_component}"
            hashed_id = hashlib.sha256(raw_id.encode()).digest()  # Get bytes
            return base58.b58encode(hashed_id).decode()  # Base58 encode
        return v


class ConnectorPair(BaseModel):
    connector_name: str
    trading_pair: str

    def is_amm_connector(self) -> bool:
        return self.connector_name in sorted(
            AllConnectorSettings.get_gateway_amm_connector_names()
        )


class PositionSummary(BaseModel):
    connector_name: str
    trading_pair: str
    volume_traded_quote: Decimal
    side: TradeType
    amount: Decimal
    breakeven_price: Decimal
    unrealized_pnl_quote: Decimal
    realized_pnl_quote: Decimal
    cum_fees_quote: Decimal

    @property
    def amount_quote(self) -> Decimal:
        return self.amount * self.breakeven_price

    @property
    def global_pnl_quote(self) -> Decimal:
        return self.unrealized_pnl_quote + self.realized_pnl_quote - self.cum_fees_quote
