import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.liquidations_feed.agentfeed import AgentFeedLiquidations, constants as CONSTANTS
from hummingbot.data_feed.liquidations_feed.liquidations_base import LiquidationSide

TEST_KEY = "afk_TestKeyThatMustNeverAppearInALog0123456789"
FEED_URL = re.compile(r"^https://x402\.ochinimus\.app/api/liq-feed.*$")


class TestAgentFeedLiquidations(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.feed = AgentFeedLiquidations(trading_pairs={"BTC-USDT", "ETH-USDT"}, max_retention_seconds=60,
                                          api_key=TEST_KEY, poll_interval_seconds=30)
        self.log_records = []
        self.feed.logger().setLevel(1)
        self.feed.logger().addHandler(self)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await self.feed._fetch_and_map_trading_pairs()

    def handle(self, record):
        self.log_records.append(record)

    def logged(self, log_level: str, fragment: str) -> int:
        return len([r for r in self.log_records if r.levelname == log_level and fragment in r.getMessage()])

    @staticmethod
    def bucket(t: int, symbol: str, longs=None, shorts=None):
        return {"t": t, "symbol": symbol, "longs": longs, "shorts": shorts, "dominant": "longs", "pressure": 12}

    def answer(self, buckets, next_cursor="1792066670000.6086000", has_more=False):
        return {"tool": "get_liq_feed", "data": {"source": "cross-venue liquidation pressure, computed by AgentFeed",
                                                 "bucket_s": 5, "settle_s": 10, "as_of": 1792066670000, "count": len(buckets),
                                                 "has_more": has_more, "next": next_cursor, "buckets": buckets}}

    def test_name_and_urls(self):
        self.assertEqual("agentfeed_liquidations", self.feed.name)
        self.assertEqual("https://x402.ochinimus.app", self.feed.rest_url)
        self.assertEqual("https://x402.ochinimus.app/api/sample", self.feed.health_check_url)

    def test_poll_interval_has_a_floor(self):
        feed = AgentFeedLiquidations(trading_pairs=set(), max_retention_seconds=60, api_key=TEST_KEY, poll_interval_seconds=1)
        self.assertEqual(CONSTANTS.MIN_POLL_INTERVAL_SECONDS, feed._poll_interval)
        feed = AgentFeedLiquidations(trading_pairs=set(), max_retention_seconds=60, api_key=TEST_KEY)
        self.assertEqual(CONSTANTS.DEFAULT_POLL_INTERVAL_SECONDS, feed._poll_interval)

    def test_too_many_pairs_is_refused_up_front(self):
        pairs = {f"A{i}-USDT" for i in range(21)}
        with self.assertRaises(ValueError):
            AgentFeedLiquidations(trading_pairs=pairs, max_retention_seconds=60, api_key=TEST_KEY)

    async def test_non_usdt_pair_is_refused(self):
        feed = AgentFeedLiquidations(trading_pairs={"BTC-USD"}, max_retention_seconds=60, api_key=TEST_KEY)
        with self.assertRaises(ValueError):
            await feed._fetch_and_map_trading_pairs()

    async def test_symbols_param(self):
        self.assertEqual("BTCUSDT,ETHUSDT", self.feed._symbols_param())
        feed = AgentFeedLiquidations(trading_pairs=None, max_retention_seconds=60, api_key=TEST_KEY)
        self.assertIsNone(feed._symbols_param())

    async def test_store_buckets_emits_one_liquidation_per_symbol_side_and_bucket(self):
        self.feed._store_buckets([
            self.bucket(1792066550000, "BTCUSDT", longs={"usd": 250000, "qty": 3.1, "vwap": 80500}),
            self.bucket(1792066555000, "ETHUSDT", longs={"usd": 55000, "qty": 23, "vwap": 2350},
                        shorts={"usd": 4000, "qty": 1.7, "vwap": 2360}),
            self.bucket(1792066555000, "PEPEUSDT", shorts={"usd": 90, "qty": 9000000, "vwap": 0.00001}),
            self.bucket(1792066555000, "BTCEUR", shorts={"usd": 90, "qty": 1, "vwap": 90}),
        ])
        btc = self.feed.liquidations_df("BTC-USDT")
        self.assertEqual(1, len(btc))
        self.assertEqual([1792066550000, "BTC-USDT", 3.1, 80500.0, LiquidationSide.LONG], list(btc.iloc[0]))
        eth = self.feed.liquidations_df("ETH-USDT")
        self.assertEqual({LiquidationSide.LONG, LiquidationSide.SHORT}, set(eth["side"]))
        self.assertEqual(1, len(self.feed.liquidations_df("PEPE-USDT")), "a pair not asked for by name is mapped by its USDT suffix")
        self.assertEqual(4, len(self.feed.liquidations_df()), "the non-USDT symbol is skipped")

    async def test_store_buckets_does_not_repeat_a_bucket(self):
        bucket = self.bucket(1792066550000, "BTCUSDT", longs={"usd": 250000, "qty": 3.1, "vwap": 80500})
        self.feed._store_buckets([bucket])
        self.feed._store_buckets([bucket])
        self.assertEqual(1, len(self.feed.liquidations_df("BTC-USDT")))

    async def test_first_poll_sends_since_and_the_key_then_the_cursor(self):
        with aioresponses() as mock:
            mock.get(FEED_URL, body=json.dumps(self.answer([self.bucket(1792066550000, "BTCUSDT", longs={"usd": 1, "qty": 1, "vwap": 1})])))
            mock.get(FEED_URL, body=json.dumps(self.answer([], next_cursor="1792066675000.6086100")))
            with patch("time.time", return_value=1792066700.0):
                self.assertFalse(await self.feed._poll_once())
            self.assertFalse(await self.feed._poll_once())
            calls = [call for key, calls in mock.requests.items() for call in calls]
            first, second = calls[0], calls[1]
            self.assertEqual(TEST_KEY, first.kwargs["headers"][CONSTANTS.API_KEY_HEADER])
            self.assertEqual({"symbols": "BTCUSDT,ETHUSDT", "since": 1792066700000 - 60000}, dict(first.kwargs["params"]))
            self.assertEqual({"symbols": "BTCUSDT,ETHUSDT", "next": "1792066670000.6086000"}, dict(second.kwargs["params"]))
        self.assertTrue(self.feed._polled_once)
        self.assertEqual("1792066675000.6086100", self.feed._cursor)

    async def test_has_more_is_reported_so_the_next_page_is_immediate(self):
        with aioresponses() as mock:
            mock.get(FEED_URL, body=json.dumps(self.answer([], has_more=True)))
            self.assertTrue(await self.feed._poll_once())

    async def test_ready_only_after_the_first_answer(self):
        self.feed._subscribed_to_channels = True
        self.assertFalse(self.feed.ready)
        with aioresponses() as mock:
            mock.get(FEED_URL, body=json.dumps(self.answer([])))
            await self.feed._poll_once()
        self.assertTrue(self.feed.ready)

    async def run_listener(self, mock_setup, sleeps=3):
        delays = []

        async def fake_sleep(delay):
            delays.append(delay)
            if len(delays) >= sleeps:
                raise asyncio.CancelledError

        self.feed._sleep = fake_sleep
        with aioresponses() as mock:
            mock_setup(mock)
            with self.assertRaises(asyncio.CancelledError):
                await self.feed.listen_for_subscriptions()
        return delays

    async def test_a_refused_key_logs_one_line_leaves_the_feed_not_ready_and_does_not_spin(self):
        self.feed._subscribed_to_channels = True
        for status in (401, 402):
            self.log_records.clear()
            self.feed._last_problem = None
            delays = await self.run_listener(lambda m: [m.get(FEED_URL, status=status, body='{"error":"x"}') for _ in range(3)], sleeps=3)
            self.assertEqual([CONSTANTS.AUTH_RETRY_SECONDS] * 3, delays)
            self.assertEqual(1, self.logged("ERROR", "AgentFeed refused the API key"), f"status {status}")
            self.assertFalse(self.feed.ready)

    async def test_a_missing_key_makes_no_request_and_logs_once(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop(CONSTANTS.API_KEY_ENV_VAR, None)
            feed = AgentFeedLiquidations(trading_pairs={"BTC-USDT"}, max_retention_seconds=60)
        feed.logger().addHandler(self)
        feed._subscribed_to_channels = True
        delays = []

        async def fake_sleep(delay):
            delays.append(delay)
            if len(delays) >= 3:
                raise asyncio.CancelledError

        feed._sleep = fake_sleep
        with aioresponses():  # no mocks: any request would raise
            with self.assertRaises(asyncio.CancelledError):
                await feed.listen_for_subscriptions()
        self.assertEqual(1, self.logged("ERROR", "no API key"))
        self.assertFalse(feed.ready)

    async def test_the_key_comes_from_the_environment(self):
        with patch.dict("os.environ", {CONSTANTS.API_KEY_ENV_VAR: "  afk_FromEnv  "}):
            feed = AgentFeedLiquidations(trading_pairs={"BTC-USDT"}, max_retention_seconds=60)
        self.assertEqual("afk_FromEnv", feed._api_key)

    async def test_rate_limited_waits_the_retry_after(self):
        self.feed._subscribed_to_channels = True
        delays = await self.run_listener(lambda m: m.get(FEED_URL, status=429, headers={"Retry-After": "7"}, body="{}"), sleeps=1)
        self.assertEqual([7.0], delays)

    async def test_a_rejected_cursor_restarts_from_the_retention_window(self):
        self.feed._cursor = "1700000000000.5"
        with aioresponses() as mock:
            mock.get(FEED_URL, status=400, body='{"error":"next is older than the 24 h this route serves"}')
            self.assertTrue(await self.feed._poll_once())
        self.assertIsNone(self.feed._cursor)
        self.assertEqual(1, self.logged("WARNING", "no longer accepts the saved cursor"))

    async def test_a_network_error_backs_off_and_logs_once(self):
        self.feed._subscribed_to_channels = True
        delays = await self.run_listener(lambda m: [m.get(FEED_URL, status=500, body="boom") for _ in range(3)], sleeps=3)
        self.assertEqual([60.0, 120.0, 240.0], delays)
        self.assertEqual(1, self.logged("WARNING", "AgentFeed liquidations poll failed"))

    async def test_polling_waits_the_poll_interval_between_answers(self):
        body = json.dumps(self.answer([]))
        delays = await self.run_listener(lambda m: [m.get(FEED_URL, body=body) for _ in range(2)], sleeps=2)
        self.assertEqual([30.0, 30.0], delays)

    async def test_the_key_is_never_logged(self):
        self.feed._subscribed_to_channels = True
        await self.run_listener(lambda m: [m.get(FEED_URL, status=401, body='{"error":"unknown key"}') for _ in range(2)], sleeps=2)
        for record in self.log_records:
            self.assertNotIn(TEST_KEY, record.getMessage())
            self.assertNotIn(TEST_KEY, str(record.args))
        self.assertNotIn(TEST_KEY, repr(self.feed))

    async def test_check_network(self):
        with aioresponses() as mock:
            mock.get(self.feed.health_check_url, body="{}")
            self.assertEqual(NetworkStatus.CONNECTED, await self.feed.check_network())

    async def test_start_network_maps_pairs_and_marks_subscribed(self):
        feed = AgentFeedLiquidations(trading_pairs={"SOL-USDT"}, max_retention_seconds=60, api_key=TEST_KEY)
        with patch.object(feed, "listen_for_subscriptions", new=AsyncMock()), \
                patch.object(feed, "_cleanup_old_liquidations_loop", new=AsyncMock()):
            await feed.start_network()
            await asyncio.sleep(0)
        self.assertEqual("SOLUSDT", feed.get_exchange_trading_pair("SOL-USDT"))
        self.assertFalse(feed.ready, "not ready until the first answer")
        await feed.stop_network()
