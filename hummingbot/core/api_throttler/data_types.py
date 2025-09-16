"""
Data types for API throttler.
Minimal implementation to support connector development.
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class RateLimitType(Enum):
    """Rate limit types."""
    REQUEST_WEIGHT = "REQUEST_WEIGHT"
    RAW_REQUEST = "RAW_REQUEST"


@dataclass
class LinkedLimitWeightPair:
    """Linked limit weight pair for rate limiting."""
    limit_id: str
    weight: int = 1


@dataclass
class RateLimit:
    """Rate limit configuration."""
    limit_id: str
    limit: int
    time_interval: float
    linked_limits: Optional[list] = None
    weight: int = 1
