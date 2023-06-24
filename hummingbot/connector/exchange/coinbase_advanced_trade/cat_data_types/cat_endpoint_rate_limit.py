from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Protocol, Union

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

from .cat_api_v3_enums import CoinbaseAdvancedTradeRateLimitType as _RateLimitType


class CoinbaseAdvancedTradeEndpointProtocol(Protocol):
    @classmethod
    def limit_id(cls) -> str:
        ...


class CoinbaseAdvancedTradeRateLimitProtocol(Protocol):
    @classmethod
    def rate_limit_type(cls) -> _RateLimitType:
        ...

    @classmethod
    def rate_limit(cls) -> int:
        ...

    @classmethod
    def interval(cls) -> int:
        ...

    @classmethod
    def weight(cls) -> int:
        ...

    @classmethod
    def limit_id(cls) -> str:
        ...

    @classmethod
    def linked_limits(cls) -> Optional[List[LinkedLimitWeightPair]]:
        ...


class _RateLimitPtl(CoinbaseAdvancedTradeRateLimitProtocol):
    REQ_TO_RATE_LIMIT_MAP: Dict[_RateLimitType, RateLimit]
    RATE_LIMITS: List[RateLimit]


class CoinbaseAdvancedTradeEndpointRateLimit(ABC):
    """
    This class is used to define the rate limits for each endpoint.
    """
    ONE_SECOND: int = 1
    ONE_MINUTE: int = 60
    ONE_HOUR: int = 3600
    ONE_DAY: int = 86400

    REQUESTS: Dict[Union[str, _RateLimitType], Dict] = {
        _RateLimitType.REST: {"name": "REST", "limit": 20, "interval": ONE_SECOND},
        _RateLimitType.SIGNIN: {"name": "SIGNIN", "limit": 10000, "interval": ONE_HOUR},
        _RateLimitType.WSS: {"name": "WSS", "limit": 750, "interval": ONE_SECOND},
    }

    # Create a map of the request type to the rate limit object
    REQ_TO_RATE_LIMIT_MAP: Dict[_RateLimitType, RateLimit] = {
        k: RateLimit(limit_id=v["name"], limit=v["limit"], time_interval=v["interval"]) for k, v in REQUESTS.items()
    }

    # Create a list of all the base rate limits
    RATE_LIMITS = [v for v in REQ_TO_RATE_LIMIT_MAP.values()]

    def __init_subclass__(cls: _RateLimitPtl, **kwargs):

        # The subclass can overwrite the default rate limit values, often the default values are used
        limit_id = cls.limit_id()
        limit: int = cls.rate_limit()
        interval: float = cls.interval()
        weight: int = cls.weight()
        linked_limits: List[LinkedLimitWeightPair] = cls.linked_limits()

        rate_limit = RateLimit(
            limit_id=limit_id,
            limit=limit,
            time_interval=interval,
            weight=weight,
            linked_limits=linked_limits
        )

        if rate_limit not in cls.RATE_LIMITS:
            cls.RATE_LIMITS.append(rate_limit)

            # TODO: Convince HB team to adopt this RateLimit register and remove the following lines
            import hummingbot.connector.exchange.coinbase_advanced_trade.cat_constants as CONSTANTS
            CONSTANTS.RATE_LIMITS.append(rate_limit)

        # Initialize this class's rate limit object
        super().__init_subclass__(**kwargs)

    @classmethod
    @abstractmethod
    def linked_limit(cls) -> _RateLimitType:
        """
        Get the rate limit type for the API endpoint.
        :return: The rate limit type.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def limit_id(cls) -> str:
        """
        Get the rate limit identifier for the API endpoint.
        :return: The rate limit identifier.
        """
        raise NotImplementedError(f"{cls.__name__} does not implement the `limit_id` method")

    @classmethod
    def rate_limit(cls) -> int:
        """
        Get the rate limit value for the API endpoint.
        :return: The rate limit value.
        """
        _type: _RateLimitType = cls.linked_limit()
        return cls.REQ_TO_RATE_LIMIT_MAP[_type].limit

    @classmethod
    def interval(cls) -> float:
        """
        Get the rate limit time interval for the API endpoint.
        :return: The rate limit time interval.
        """
        _type: _RateLimitType = cls.linked_limit()
        return cls.REQ_TO_RATE_LIMIT_MAP[_type].time_interval

    @classmethod
    def weight(cls) -> int:
        """
        Get the rate limit time interval for the API endpoint.
        :return: The rate limit time interval.
        """
        _type: _RateLimitType = cls.linked_limit()
        return cls.REQ_TO_RATE_LIMIT_MAP[_type].weight

    @classmethod
    def linked_limits(cls) -> Optional[List[LinkedLimitWeightPair]]:
        """
        Get the linked limits for the API endpoint.
        :return: The linked limits.
        """
        _type: _RateLimitType = cls.linked_limit()
        return [
            LinkedLimitWeightPair(
                limit_id=cls.REQ_TO_RATE_LIMIT_MAP[_type].limit_id,
                weight=1
            )
        ]
