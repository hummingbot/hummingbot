import unittest

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_enums import (
    CoinbaseAdvancedTradeRateLimitType as _RateLimitType,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_endpoint_rate_limit import (
    CoinbaseAdvancedTradeEndpointRateLimit,
)
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit


class TestCoinbaseAdvancedTradeEndpointRateLimit(unittest.TestCase):
    class MockEndpoint(CoinbaseAdvancedTradeEndpointRateLimit):
        @classmethod
        def endpoint(cls) -> str:
            return "mock_endpoint"

        @classmethod
        def rate_limit_type(cls) -> _RateLimitType:
            return _RateLimitType.REST

        @classmethod
        def limit_id(cls) -> str:
            return "MockEndpoint"

    def test_0_requests(self):
        requests = CoinbaseAdvancedTradeEndpointRateLimit.REQUESTS
        expected_requests = {
            _RateLimitType.REST: {"name": "REST", "limit": 20,
                                  "interval": CoinbaseAdvancedTradeEndpointRateLimit.ONE_SECOND},
            _RateLimitType.SIGNIN: {"name": "SIGNIN", "limit": 10000,
                                    "interval": CoinbaseAdvancedTradeEndpointRateLimit.ONE_HOUR},
            _RateLimitType.WSS: {"name": "WSS", "limit": 750,
                                 "interval": CoinbaseAdvancedTradeEndpointRateLimit.ONE_SECOND},
        }
        self.assertEqual(expected_requests, requests, "Requests are not equal. This is an expected failure if the API "
                                                      "has changed. Simply reset the expected constant test values")

    def test_request_mapping(self):
        requests = CoinbaseAdvancedTradeEndpointRateLimit.REQUESTS
        request_map = CoinbaseAdvancedTradeEndpointRateLimit.REQ_TO_RATE_LIMIT_MAP
        expected_request_map = {
            _RateLimitType.REST: RateLimit(limit_id=requests[_RateLimitType.REST]["name"],
                                           limit=requests[_RateLimitType.REST]["limit"],
                                           time_interval=requests[_RateLimitType.REST]["interval"]),
            _RateLimitType.SIGNIN: RateLimit(limit_id=requests[_RateLimitType.SIGNIN]["name"],
                                             limit=requests[_RateLimitType.SIGNIN]["limit"],
                                             time_interval=requests[_RateLimitType.SIGNIN]["interval"]),
            _RateLimitType.WSS: RateLimit(limit_id=requests[_RateLimitType.WSS]["name"],
                                          limit=requests[_RateLimitType.WSS]["limit"],
                                          time_interval=requests[_RateLimitType.WSS]["interval"]),
        }
        # There is an issue with the RateLimit object's __eq__ method, so we have to compare the string representations
        self.assertEqual(str(expected_request_map), str(request_map))

    def test_rate_limit_list(self):
        requests = CoinbaseAdvancedTradeEndpointRateLimit.REQUESTS
        rate_limits = CoinbaseAdvancedTradeEndpointRateLimit.RATE_LIMITS
        expected_rate_limits = [
            RateLimit(limit_id=requests[_RateLimitType.REST]["name"],
                      limit=requests[_RateLimitType.REST]["limit"],
                      time_interval=requests[_RateLimitType.REST]["interval"]),
            RateLimit(limit_id=requests[_RateLimitType.SIGNIN]["name"],
                      limit=requests[_RateLimitType.SIGNIN]["limit"],
                      time_interval=requests[_RateLimitType.SIGNIN]["interval"]),
            RateLimit(limit_id=requests[_RateLimitType.WSS]["name"],
                      limit=requests[_RateLimitType.WSS]["limit"],
                      time_interval=requests[_RateLimitType.WSS]["interval"]),
        ]
        # We have a subclass that adds its own rate limit, so let's verify that the default
        # expected list is at the beginning of the rate limit list
        [self.assertIn(str(e), str(a)) for e, a in zip(expected_rate_limits, rate_limits)]

    def test_init_subclass_rest(self):
        for rate_limit_type in _RateLimitType:
            class CustomEndpoint(CoinbaseAdvancedTradeEndpointRateLimit):
                @classmethod
                def endpoint(cls) -> str:
                    return "custom_endpoint"

                @classmethod
                def rate_limit_type(cls) -> _RateLimitType:
                    return rate_limit_type

                @classmethod
                def limit_id(cls) -> str:
                    return "CustomEndpoint"

            expected_rate_limit = CoinbaseAdvancedTradeEndpointRateLimit.REQUESTS[rate_limit_type]["limit"]
            expected_interval = CoinbaseAdvancedTradeEndpointRateLimit.REQUESTS[rate_limit_type]["interval"]

            self.assertEqual(expected_rate_limit, CustomEndpoint.rate_limit())
            self.assertEqual(expected_interval, CustomEndpoint.interval())
            self.assertEqual("CustomEndpoint", CustomEndpoint.limit_id(), )
            self.assertTrue(any(limit.limit_id == "CustomEndpoint" for limit in CustomEndpoint.RATE_LIMITS))

            # Instantiation
            custom_endpoint = CustomEndpoint()
            self.assertEqual(expected_rate_limit, custom_endpoint.rate_limit())
            self.assertEqual(expected_interval, custom_endpoint.interval(), 1)
            self.assertEqual("CustomEndpoint", custom_endpoint.limit_id(), )
            self.assertTrue(any(limit.limit_id == "CustomEndpoint" for limit in custom_endpoint.RATE_LIMITS))

    def test_subclass_override(self):
        class OverrideEndpoint(CoinbaseAdvancedTradeEndpointRateLimit):
            @classmethod
            def endpoint(cls) -> str:
                return "override_endpoint"

            @classmethod
            def rate_limit_type(cls) -> _RateLimitType:
                return _RateLimitType.REST

            @classmethod
            def limit_id(cls) -> str:
                return "override_limit_id"

            @classmethod
            def rate_limit(cls) -> int:
                return 50

            @classmethod
            def interval(cls) -> float:
                return 2

            @classmethod
            def linked_limits(cls):
                return [
                    LinkedLimitWeightPair(limit_id="LINKED_LIMIT", weight=2)
                ]

        override_endpoint = OverrideEndpoint()
        self.assertEqual(50, override_endpoint.rate_limit())
        self.assertEqual(2, override_endpoint.interval())
        self.assertEqual("override_limit_id", override_endpoint.limit_id())
        self.assertFalse(any(limit.limit_id == "override_endpoint" for limit in override_endpoint.RATE_LIMITS))

        # Verify that the linked limit is added. We check the last item in the RATE_LIMITS list
        self.assertTrue(
            any(limit.limit_id == "LINKED_LIMIT" for limit in override_endpoint.RATE_LIMITS[-1].linked_limits))


if __name__ == "__main__":
    unittest.main()
