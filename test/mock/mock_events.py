from enum import Enum
from typing import NamedTuple


class MockEventType(Enum):
    EVENT_ZERO = 0
    EVENT_ONE = 1


class MockEvent(NamedTuple):
    payload: int
