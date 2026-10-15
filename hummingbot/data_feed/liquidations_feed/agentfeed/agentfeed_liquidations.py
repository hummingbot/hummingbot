import asyncio
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set

from bidict import bidict

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.data_feed.liquidations_feed.agentfeed import constants as CONSTANTS
from hummingbot.data_feed.liquidations_feed.liquidations_base import Liquidation, LiquidationsBase, LiquidationSide
from hummingbot.logger import HummingbotLogger


class AgentFeedAPIKeyAppender(RESTPreProcessorBase):
    """Adds the AgentFeed prepaid key to every request as a header. The key is never logged."""

    def __init__(self, api_key: str):
        super().__init__()
        self._api_key = api_key

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers or {}
        if self._api_key:
            request.headers[CONSTANTS.API_KEY_HEADER] = self._api_key
        return request


class AgentFeedAuthError(Exception):
    """The key is missing, unknown, revoked or out of balance (HTTP 401 or 402)."""


class AgentFeedRateLimited(Exception):
    """The server asked for a slower poll (HTTP 429)."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after:.0f}s")
        self.retry_after = retry_after


class AgentFeedLiquidations(LiquidationsBase):
    """
    Liquidations from AgentFeed's /api/liq-feed, polled over REST.

    What it returns is cross-venue liquidation pressure computed by AgentFeed: for every symbol and every closed 5-second
    bucket that held a liquidation, the USD, base quantity and VWAP of the long and of the short positions liquidated, all
    venues combined. It is not a stream of individual liquidations: one `Liquidation` is emitted per symbol, side and
    bucket, with `quantity` the summed base quantity and `price` the VWAP, both rounded by the server (2 and 3 significant
    figures). `timestamp` is the start of the bucket in milliseconds, in AgentFeed's stream time.

    The route is paid (about $1.44 a day for a 30 s poll on a prepaid key, $0.0005 a call). The key comes from the
    `api_key` argument or the AGENTFEED_API_KEY environment variable. A missing, unknown or empty key logs one clear line,
    leaves the feed not ready and is retried slowly, without a crash loop.
    """
    _logger: Optional[HummingbotLogger] = None

    # LiquidationsFactory passes these LiquidationsConfig fields to a source that lists them
    CONFIG_FIELDS = ("api_key", "poll_interval_seconds")

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 trading_pairs: Optional[Set[str]],
                 max_retention_seconds: int,
                 api_key: Optional[str] = None,
                 poll_interval_seconds: Optional[float] = None):
        super().__init__(trading_pairs=trading_pairs, max_retention_seconds=max_retention_seconds)
        pairs = sorted(trading_pairs or [])
        if len(pairs) > CONSTANTS.MAX_SYMBOLS:
            raise ValueError(f"AgentFeed serves at most {CONSTANTS.MAX_SYMBOLS} symbols per feed, got {len(pairs)}")
        self._api_key = (api_key or os.environ.get(CONSTANTS.API_KEY_ENV_VAR, "")).strip()
        self._poll_interval = max(CONSTANTS.MIN_POLL_INTERVAL_SECONDS,
                                  float(poll_interval_seconds or CONSTANTS.DEFAULT_POLL_INTERVAL_SECONDS))
        # the key rides on every request through a pre-processor, the way the CoinCap data feed sends its key
        self._api_factory = WebAssistantsFactory(
            throttler=AsyncThrottler(rate_limits=self.rate_limits),
            rest_pre_processors=[AgentFeedAPIKeyAppender(api_key=self._api_key)],
        )
        self._cursor: Optional[str] = None
        self._polled_once = False
        self._auth_failed = False
        self._last_problem: Optional[str] = None
        self._seen: "OrderedDict[tuple, None]" = OrderedDict()

    @property
    def name(self):
        return "agentfeed_liquidations"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        return ""  # polled over REST

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def ready(self):
        """True once the first poll has been answered, and not while the key is refused."""
        return self._subscribed_to_channels and self._polled_once and not self._auth_failed

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return self._trading_pairs_map.inverse.get(trading_pair)

    async def _fetch_and_map_trading_pairs(self):
        """
        AgentFeed names a perpetual BASEUSDT. The requested Hummingbot pairs (BASE-USDT) map one to one, so nothing is
        fetched. With no pairs asked for, the route serves its five majors and the other direction is mapped by name.
        """
        self._trading_pairs_map = bidict()
        for trading_pair in sorted(self._trading_pairs or []):
            base, _, quote = trading_pair.partition("-")
            if not base or quote != "USDT":
                raise ValueError(f"AgentFeed liquidations cover USDT perpetuals only, got {trading_pair}")
            self._trading_pairs_map[f"{base}{quote}"] = trading_pair

    @staticmethod
    def _hb_pair(exchange_symbol: str) -> Optional[str]:
        if exchange_symbol.endswith("USDT") and len(exchange_symbol) > 4:
            return f"{exchange_symbol[:-4]}-USDT"
        return None

    def _symbols_param(self) -> Optional[str]:
        if not self._trading_pairs:
            return None  # the route's default set
        return ",".join(self.get_exchange_trading_pair(pair) for pair in sorted(self._trading_pairs))

    async def listen_for_subscriptions(self):
        """
        Polls /api/liq-feed with the cursor the last answer returned. A refused key, a rate limit and a network error each
        wait and retry quietly: one log line per kind of problem, not one per attempt.
        """
        errors_in_a_row = 0
        while True:
            try:
                if not self._api_key:
                    self._report_problem(
                        f"no API key: set {CONSTANTS.API_KEY_ENV_VAR} or pass api_key. Buy one at {CONSTANTS.REST_URL}/keys. "
                        "The AgentFeed liquidations feed is not ready.")
                    self._auth_failed = True
                    await self._sleep(CONSTANTS.AUTH_RETRY_SECONDS)
                    continue
                has_more = await self._poll_once()
                errors_in_a_row = 0
                await self._sleep(0.0 if has_more else self._poll_interval)
            except asyncio.CancelledError:
                raise
            except AgentFeedAuthError as auth_error:
                self._auth_failed = True
                self._report_problem(f"AgentFeed refused the API key ({auth_error}). The liquidations feed is not ready; "
                                     f"checking again every {int(CONSTANTS.AUTH_RETRY_SECONDS)}s.")
                await self._sleep(CONSTANTS.AUTH_RETRY_SECONDS)
            except AgentFeedRateLimited as limited:
                await self._sleep(max(limited.retry_after, 1.0))
            except Exception as error:
                errors_in_a_row += 1
                self._report_problem(f"AgentFeed liquidations poll failed ({error}); retrying with backoff.", is_error=False)
                await self._sleep(min(self._poll_interval * (2 ** min(errors_in_a_row, 4)), CONSTANTS.MAX_BACKOFF_SECONDS))

    def _report_problem(self, message: str, is_error: bool = True):
        """Logs a problem once: the same message is not repeated on every retry."""
        if message != self._last_problem:
            self._last_problem = message
            if is_error:
                self.logger().error(message)
            else:
                self.logger().warning(message)

    async def _poll_once(self) -> bool:
        params: Dict[str, Any] = {}
        symbols = self._symbols_param()
        if symbols:
            params["symbols"] = symbols
        if self._cursor:
            params["next"] = self._cursor
        else:
            params["since"] = int(time.time() * 1000) - min(self._max_retention_seconds, 24 * 3600) * 1000
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request_and_get_response(
            url=self.rest_url + CONSTANTS.LIQUIDATIONS_ENDPOINT,
            throttler_limit_id=CONSTANTS.LIQUIDATIONS_ENDPOINT,
            params=params,
            method=RESTMethod.GET,
            return_err=True,
        )
        status = response.status
        if status in (401, 402):
            raise AgentFeedAuthError(f"HTTP {status}")
        if status == 429:
            raise AgentFeedRateLimited(float(response.headers.get("Retry-After", CONSTANTS.MIN_POLL_INTERVAL_SECONDS)))
        if status == 400 and self._cursor:
            # the cursor is older than the 24 h the server keeps, or unknown to it: start again from the retention window
            self.logger().warning("AgentFeed no longer accepts the saved cursor; restarting from the retention window.")
            self._cursor = None
            return True
        if status >= 400:
            raise IOError(f"HTTP {status}")
        body = await response.json()
        data = body["data"]
        self._store_buckets(data.get("buckets", []))
        self._cursor = data["next"]
        self._polled_once = True
        self._auth_failed = False
        self._last_problem = None
        return bool(data.get("has_more"))

    def _store_buckets(self, buckets: List[Dict[str, Any]]):
        for bucket in buckets:
            trading_pair = self._trading_pairs_map.get(bucket["symbol"]) or self._hb_pair(bucket["symbol"])
            if trading_pair is None:
                continue
            for key, side in (("longs", LiquidationSide.LONG), ("shorts", LiquidationSide.SHORT)):
                part = bucket.get(key)
                if not part:
                    continue
                seen_key = (bucket["t"], trading_pair, side)
                if seen_key in self._seen:
                    continue
                self._seen[seen_key] = None
                while len(self._seen) > CONSTANTS.SEEN_BUCKETS_LIMIT:
                    self._seen.popitem(last=False)
                self._liquidations.setdefault(trading_pair, []).append(Liquidation(
                    timestamp=int(bucket["t"]),
                    trading_pair=trading_pair,
                    quantity=float(part["qty"]),
                    price=float(part["vwap"]),
                    side=side))
