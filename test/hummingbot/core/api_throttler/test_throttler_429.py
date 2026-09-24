import asyncio
import time
import unittest
from unittest.mock import MagicMock, patch

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.api_throttler.async_throttler import AsyncRequestContext, AsyncThrottler
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant, retry_after_from_headers

LIMIT_ID = "test_limit"


class RetryAfterHeaderTests(unittest.TestCase):
    NOW = 1_700_000_000.0

    def _parse(self, headers):
        return retry_after_from_headers(headers, now=self.NOW)

    def test_returns_none_without_a_known_header(self):
        self.assertIsNone(self._parse({}))
        self.assertIsNone(self._parse({"Content-Type": "application/json"}))

    def test_retry_after_is_read_as_a_delay(self):
        self.assertEqual(30.0, self._parse({"Retry-After": "30"}))

    def test_retry_after_wins_over_the_draft_headers(self):
        self.assertEqual(5.0, self._parse({"Retry-After": "5", "RateLimit-Reset": "99"}))

    def test_ratelimit_reset_is_read_as_a_delay(self):
        self.assertEqual(12.0, self._parse({"RateLimit-Reset": "12"}))
        self.assertEqual(7.0, self._parse({"X-RateLimit-Reset": "7"}))

    def test_an_epoch_value_is_converted_to_a_delay(self):
        self.assertEqual(45.0, self._parse({"RateLimit-Reset": str(self.NOW + 45)}))

    def test_an_epoch_in_milliseconds_is_converted_to_a_delay(self):
        self.assertEqual(45.0, self._parse({"RateLimit-Reset": str((self.NOW + 45) * 1000)}))

    def test_unparseable_values_are_ignored(self):
        self.assertIsNone(self._parse({"Retry-After": ""}))
        self.assertIsNone(self._parse({"Retry-After": "soon"}))

    def test_an_unparseable_value_falls_through_to_the_next_header(self):
        self.assertEqual(12.0, self._parse({"Retry-After": "soon", "RateLimit-Reset": "12"}))

    def test_retry_after_as_an_http_date_is_converted_to_a_delay(self):
        # NOW is 2023-11-14 22:13:20 GMT, so this is 60s later.
        self.assertEqual(60.0, self._parse({"Retry-After": "Tue, 14 Nov 2023 22:14:20 GMT"}))

    def test_an_http_date_is_measured_against_the_servers_clock(self):
        # Our clock is 100s ahead of the exchange's. The wait should still be 60s.
        headers = {"Date": "Tue, 14 Nov 2023 22:11:40 GMT", "Retry-After": "Tue, 14 Nov 2023 22:12:40 GMT"}
        self.assertEqual(60.0, self._parse(headers))

    def test_an_epoch_is_measured_against_the_servers_clock(self):
        server_now = self.NOW - 100
        headers = {"Date": "Tue, 14 Nov 2023 22:11:40 GMT", "RateLimit-Reset": str(server_now + 45)}
        self.assertEqual(45.0, self._parse(headers))

    def test_a_delay_is_not_affected_by_the_date_header(self):
        self.assertEqual(30.0, self._parse({"Date": "Tue, 14 Nov 2023 22:11:40 GMT", "Retry-After": "30"}))


class PauseAfterTooManyRequestsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.throttler = AsyncThrottler(
            rate_limits=[RateLimit(limit_id=LIMIT_ID, limit=100, time_interval=1)]
        )

    def tearDown(self) -> None:
        self.loop.close()

    def _context(self):
        return self.throttler.execute_task(limit_id=LIMIT_ID)

    def test_pause_blocks_further_capacity_for_that_limit(self):
        self.assertTrue(self._context().within_capacity())

        self.loop.run_until_complete(
            self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=30)
        )

        self.assertFalse(self._context().within_capacity())

    def test_capacity_returns_once_the_pause_elapses(self):
        self.loop.run_until_complete(
            self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=30)
        )
        self.assertFalse(self._context().within_capacity())

        # within_capacity() reads the clock through the context, so move that forward.
        with patch.object(AsyncRequestContext, "_time", return_value=time.time() + 31):
            self.assertTrue(self._context().within_capacity())

    def test_pause_only_affects_the_limit_that_was_throttled(self):
        other = "other_limit"
        self.throttler.set_rate_limits([
            RateLimit(limit_id=LIMIT_ID, limit=100, time_interval=1),
            RateLimit(limit_id=other, limit=100, time_interval=1),
        ])

        self.loop.run_until_complete(
            self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=30)
        )

        self.assertFalse(self.throttler.execute_task(limit_id=LIMIT_ID).within_capacity())
        self.assertTrue(self.throttler.execute_task(limit_id=other).within_capacity())

    def test_nonpositive_retry_after_does_not_pause(self):
        # The exchange is saying the limit has already reset.
        for value in (0, -5):
            with self.subTest(value=value):
                self.loop.run_until_complete(
                    self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=value)
                )
                self.assertTrue(self._context().within_capacity())

    def test_missing_retry_after_pauses_for_the_limits_own_window(self):
        self.throttler.set_rate_limits([RateLimit(limit_id=LIMIT_ID, limit=100, time_interval=10)])

        before = time.time()
        self.loop.run_until_complete(
            self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=None)
        )

        self.assertFalse(self._context().within_capacity())
        self.assertAlmostEqual(before + 10, self.throttler._resets[LIMIT_ID], delta=1)

    def test_missing_retry_after_pause_is_bounded(self):
        cases = {0.1: AsyncThrottler.MIN_DEFAULT_PAUSE_SECONDS, 86400: AsyncThrottler.MAX_DEFAULT_PAUSE_SECONDS}
        for interval, expected in cases.items():
            with self.subTest(interval=interval):
                throttler = AsyncThrottler(rate_limits=[RateLimit(limit_id=LIMIT_ID, limit=100, time_interval=interval)])
                before = time.time()
                self.loop.run_until_complete(
                    throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=None)
                )
                self.assertAlmostEqual(before + expected, throttler._resets[LIMIT_ID], delta=1)

    def test_pause_extends_to_linked_limits_and_everything_drawing_on_them(self):
        # e.g. Binance: every endpoint draws on the IP-wide request weight.
        shared = "REQUEST_WEIGHT"
        other = "other_endpoint"
        self.throttler.set_rate_limits([
            RateLimit(limit_id=shared, limit=1200, time_interval=60),
            RateLimit(limit_id=LIMIT_ID, limit=100, time_interval=1, linked_limits=[LinkedLimitWeightPair(shared, 1)]),
            RateLimit(limit_id=other, limit=100, time_interval=1, linked_limits=[LinkedLimitWeightPair(shared, 1)]),
            RateLimit(limit_id="unrelated", limit=100, time_interval=1),
        ])

        self.loop.run_until_complete(
            self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=30)
        )

        self.assertFalse(self.throttler.execute_task(limit_id=other).within_capacity())
        self.assertTrue(self.throttler.execute_task(limit_id="unrelated").within_capacity())

    def test_missing_retry_after_pauses_each_linked_limit_for_its_own_window(self):
        # The endpoint's own window is 1s, but the IP-wide weight it draws on resets every 60s,
        # and the daily order count every 24h (capped to the 60s default maximum).
        weight, daily = "REQUEST_WEIGHT", "ORDERS_24H"
        self.throttler.set_rate_limits([
            RateLimit(limit_id=weight, limit=1200, time_interval=60),
            RateLimit(limit_id=daily, limit=200000, time_interval=86400),
            RateLimit(limit_id=LIMIT_ID, limit=100, time_interval=1,
                      linked_limits=[LinkedLimitWeightPair(weight, 1), LinkedLimitWeightPair(daily, 1)]),
        ])

        before = time.time()
        self.loop.run_until_complete(
            self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=None)
        )

        self.assertAlmostEqual(before + 1, self.throttler._resets[LIMIT_ID], delta=1)
        self.assertAlmostEqual(before + 60, self.throttler._resets[weight], delta=1)
        self.assertAlmostEqual(before + AsyncThrottler.MAX_DEFAULT_PAUSE_SECONDS, self.throttler._resets[daily], delta=1)
        # The endpoint can't be used while the linked weight is paused, even after its own 1s.
        with patch.object(AsyncRequestContext, "_time", return_value=before + 5):
            self.assertFalse(self._context().within_capacity())

    def test_a_long_ban_is_waited_out_in_full(self):
        # Binance bans an IP for minutes up to days, and says how long in Retry-After.
        self.loop.run_until_complete(
            self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=3600)
        )
        remaining = self.throttler._resets[LIMIT_ID] - time.time()
        self.assertGreater(remaining, 3590)

    def test_pause_is_capped(self):
        self.loop.run_until_complete(
            self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=10 ** 9)
        )
        remaining = self.throttler._resets[LIMIT_ID] - time.time()
        self.assertLessEqual(remaining, AsyncThrottler.MAX_PAUSE_SECONDS + 1)

    def test_a_longer_pause_extends_but_a_shorter_one_does_not_shorten(self):
        run = self.loop.run_until_complete
        run(self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=60))
        longest = self.throttler._resets[LIMIT_ID]

        run(self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=5))

        self.assertEqual(longest, self.throttler._resets[LIMIT_ID])

    def test_logs_a_warning_when_pausing(self):
        logger = MagicMock()
        with patch.object(AsyncThrottler, "logger", return_value=logger):
            self.loop.run_until_complete(
                self.throttler.pause_after_too_many_requests(limit_id=LIMIT_ID, retry_after=30)
            )
        logger.warning.assert_called_once()


class RestAssistantRateLimitedResponseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()

    def tearDown(self) -> None:
        self.loop.close()

    def _execute(self, status: int, headers: dict):
        throttler = AsyncThrottler(rate_limits=[RateLimit(limit_id=LIMIT_ID, limit=100, time_interval=1)])
        url = "https://www.test.com/url"

        async def scenario():
            async with aiohttp.ClientSession() as session:
                assistant = RESTAssistant(connection=RESTConnection(session), throttler=throttler)
                with aioresponses() as mocked:
                    mocked.get(url, status=status, headers=headers, body="{}")
                    with self.assertRaises(IOError):
                        await assistant.execute_request(url=url, method=RESTMethod.GET, throttler_limit_id=LIMIT_ID)

        self.loop.run_until_complete(scenario())
        return throttler

    def test_429_pauses_the_limit(self):
        throttler = self._execute(429, {"Retry-After": "30"})
        self.assertGreater(throttler._resets[LIMIT_ID], time.time() + 25)

    def test_418_ban_pauses_the_limit(self):
        throttler = self._execute(418, {"Retry-After": "120"})
        self.assertGreater(throttler._resets[LIMIT_ID], time.time() + 115)

    def test_other_errors_do_not_pause(self):
        throttler = self._execute(400, {"Retry-After": "30"})
        self.assertNotIn(LIMIT_ID, throttler._resets)


if __name__ == "__main__":
    unittest.main()
