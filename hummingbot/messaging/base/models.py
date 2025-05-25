from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class MessageStatus(Enum):
    NEW = "new"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BrokerMessage:
    id: Optional[int]
    instance_id: str
    strategy_name: str
    command: str
    source: str
    chat_id: str
    status: MessageStatus
    created_at: datetime
    updated_at: datetime
    response: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BotInstance:
    composite_id: str
    instance_id: str
    strategy_file: str
    strategy_name: Optional[str] = None
    markets: Optional[List[str]] = None
    description: Optional[str] = None
