import hashlib
import random
import time

import base58
from pydantic import BaseModel, validator


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
