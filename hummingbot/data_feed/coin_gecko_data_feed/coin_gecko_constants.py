from dataclasses import dataclass, field
from enum import Enum
from typing import List

from hummingbot.core.api_throttler.data_types import RateLimit

# Rate limits ID
REST_CALL_RATE_LIMIT_ID = "coin_gecko_rest_rate_limit_id"


@dataclass(frozen=True)
class CoinGeckoTier:
    """Data class representing CoinGecko API tier configuration"""
    name: str  # Name used for user configuration
    header: str  # API header name to use for authentication
    base_url: str  # Base URL for the API tier
    rate_limit: int  # Calls per minute
    rate_limits: List[RateLimit] = field(default_factory=list)  # Rate limits for this tier


# API Tiers as dataclass instances with all necessary properties
PUBLIC = CoinGeckoTier(
    name="PUBLIC",
    header=None,
    base_url="https://api.coingecko.com/api/v3",
    rate_limit=10,
    rate_limits=[RateLimit(REST_CALL_RATE_LIMIT_ID, limit=10, time_interval=60)]
)

DEMO = CoinGeckoTier(
    name="DEMO",
    header="x-cg-demo-api-key",
    base_url="https://api.coingecko.com/api/v3",
    rate_limit=50,
    rate_limits=[RateLimit(REST_CALL_RATE_LIMIT_ID, limit=50, time_interval=60)]
)

PRO = CoinGeckoTier(
    name="PRO",
    header="x-cg-pro-api-key",
    base_url="https://pro-api.coingecko.com/api/v3",
    rate_limit=500,
    rate_limits=[RateLimit(REST_CALL_RATE_LIMIT_ID, limit=500, time_interval=60)]
)

# Enum for storage and selection


class CoinGeckoAPITier(Enum):
    """
    CoinGecko's Rate Limit Tiers. Based on how much money you pay them.
    """
    PUBLIC = PUBLIC
    DEMO = DEMO
    PRO = PRO


PING_REST_ENDPOINT = "/ping"
PRICES_REST_ENDPOINT = "/coins/markets"
SUPPORTED_VS_TOKENS_REST_ENDPOINT = "/simple/supported_vs_currencies"

COOLOFF_AFTER_BAN = 60.0 * 1.05

TOKEN_CATEGORIES = [
    "cryptocurrency",
    "decentralized-exchange",
    "decentralized-finance-defi",
    "smart-contract-platform",
    "stablecoins",
    "wrapped-tokens",
]
