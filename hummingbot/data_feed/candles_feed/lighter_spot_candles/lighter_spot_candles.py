import asyncio
import logging
import time
from typing import List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.lighter_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class LighterSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        self._market_id: Optional[int] = None
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"lighter_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.MAINNET_BASE_URL

    @property
    def wss_url(self):
        return CONSTANTS.MAINNET_WS_URL

    @property
    def health_check_url(self):
        return f"{CONSTANTS.MAINNET_BASE_URL}{CONSTANTS.EXCHANGE_STATS_PATH_URL}"

    @property
    def candles_url(self):
        return f"{CONSTANTS.MAINNET_BASE_URL}{CONSTANTS.CANDLES_PATH_URL}"

    @property
    def candles_endpoint(self):
        return CONSTANTS.CANDLES_PATH_URL

    @property
    def candles_max_result_per_rest_request(self):
        return CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST

    @property
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def intervals(self):
        return CONSTANTS.INTERVALS

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url,
            throttler_limit_id=CONSTANTS.EXCHANGE_STATS_PATH_URL,
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair: str) -> str:
        return trading_pair.split("-")[0].upper()

    async def initialize_exchange_data(self):
        if self._market_id is not None:
            return
        base_symbol = self._trading_pair.split("-")[0].upper()
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=f"{CONSTANTS.MAINNET_BASE_URL}{CONSTANTS.ORDER_BOOK_DETAILS_PATH_URL}",
            throttler_limit_id=CONSTANTS.ORDER_BOOK_DETAILS_PATH_URL,
        )
        for market in data.get("order_book_details", []):
            if str(market.get("symbol", "")).upper() == base_symbol:
                self._market_id = int(market["market_id"])
                break
        if self._market_id is None:
            raise ValueError(f"Lighter market not found for trading pair {self._trading_pair}")

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        now_ms = int(time.time() * 1000)
        start_ms = int(start_time * 1000) if start_time is not None else now_ms - self.interval_in_seconds * 1000
        end_ms = int(end_time * 1000) if end_time is not None else now_ms
        interval_ms = self.interval_in_seconds * 1000
        count_back = max(1, int((end_ms - start_ms) / interval_ms))
        return {
            "market_id": self._market_id,
            "resolution": CONSTANTS.INTERVALS[self.interval],
            "start_timestamp": start_ms,
            "end_timestamp": end_ms,
            "count_back": count_back,
        }

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        raw_candles = data.get("c", []) if isinstance(data, dict) else []
        result = []
        for c in raw_candles:
            ts_seconds = self.ensure_timestamp_in_seconds(c["t"])
            if end_time is not None and ts_seconds > end_time:
                continue
            result.append([
                ts_seconds,
                float(c.get("o", 0)),
                float(c.get("h", 0)),
                float(c.get("l", 0)),
                float(c.get("c", 0)),
                float(c.get("v", 0)),
                float(c.get("V", 0)),
                0.0,
                0.0,
                0.0,
            ])
        result.sort(key=lambda x: x[0])
        return result

    async def listen_for_subscriptions(self):
        # Lighter has no WebSocket candle stream — poll REST every 10 seconds
        while True:
            try:
                now_s = int(time.time())
                current_candle_end = self._round_timestamp_to_interval_multiple(now_s) + self.interval_in_seconds
                candles = await self.fetch_candles(end_time=current_candle_end, limit=1)
                if len(candles) > 0:
                    candle_row = candles[-1].astype(float)
                    if len(self._candles) == 0:
                        self._candles.append(candle_row)
                        self._ws_candle_available.set()
                        safe_ensure_future(self.fill_historical_candles())
                    else:
                        latest_ts = int(self._candles[-1][0])
                        current_ts = int(candle_row[0])
                        if current_ts > latest_ts:
                            self._candles.append(candle_row)
                        elif current_ts == latest_ts:
                            self._candles[-1] = candle_row
                await self._sleep(CONSTANTS.CANDLE_POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error polling Lighter candles. Retrying in 5s..."
                )
                await self._sleep(5.0)

    def ws_subscription_payload(self):
        return {}

    def _parse_websocket_message(self, data):
        return None
