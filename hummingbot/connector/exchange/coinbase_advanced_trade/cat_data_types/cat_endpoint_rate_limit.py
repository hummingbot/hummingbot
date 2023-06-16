from typing import List, Optional

import hummingbot.connector.exchange.coinbase_advanced_trade.cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CoinbaseAdvancedTradeAPIRequestProtocol,
)
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit


class EndpointRateLimit:
    """
    This class is used to define the rate limits for each endpoint.
    """
    ONE_SECOND = 1
    ONE_MINUTE = 60
    ONE_HOUR = 3600
    ONE_DAY = 86400

    REST_REQUESTS = "REST_REQUESTS"
    MAX_REST_REQUESTS_S = 20

    _rate_limit: RateLimit = RateLimit(limit_id=REST_REQUESTS,
                                       limit=MAX_REST_REQUESTS_S,
                                       time_interval=ONE_SECOND)

    def __init__(self, *args, **kwargs):
        if self._rate_limit not in CONSTANTS.RATE_LIMITS:
            CONSTANTS.RATE_LIMITS.append(self._rate_limit)

    def add_rate_limit(self, base_url: str):
        """
        Get the rate limit ID for the API endpoint.
        :return: The rate limit ID.
        """
        rate_limit = RateLimit(limit_id=base_url + self.limit_id,
                               limit=self.rate_limit,
                               time_interval=self.interval,
                               linked_limits=self.linked_limits)
        if rate_limit not in CONSTANTS.RATE_LIMITS:
            CONSTANTS.RATE_LIMITS.append(rate_limit)

    @property
    def rate_limit(self) -> int:
        """
        Get the rate limit value for the API endpoint.
        :return: The rate limit value.
        """
        return self.MAX_REST_REQUESTS_S

    @property
    def limit_id(self: CoinbaseAdvancedTradeAPIRequestProtocol) -> str:
        """
        Get the rate limit value for the API endpoint.
        It is customary to override this method in the child class
        when an endpoint has parametrized arguments.
        :return: The rate limit value.
        """
        return self.endpoint

    @property
    def interval(self) -> int:
        """
        Get the rate limit time interval for the API endpoint.
        :return: The rate limit time interval.
        """
        return self.ONE_SECOND

    @property
    def linked_limits(self) -> Optional[List[LinkedLimitWeightPair]]:
        """
        Get the linked limits for the API endpoint.
        :return: The linked limits.
        """
        return [LinkedLimitWeightPair(self.REST_REQUESTS, 1)]
