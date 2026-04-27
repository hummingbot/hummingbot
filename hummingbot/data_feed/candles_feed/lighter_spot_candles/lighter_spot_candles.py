import asyncio
import logging
from typing import List, Optional

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger

REST_URL = "https://mainnet.zklighter.elliot.ai/api/v1"
WSS_URL = "wss://mainnet.zklighter.elliot.ai/stream"
CANDLES_ENDPOINT = "/candles"
ORDER_BOOKS_ENDPOINT = "/orderBooks"
LIGHTER_LIMIT_ID = "LIGHTER_CANDLES_LIMIT"
LIGHTER_LIMIT = 24000
LIGHTER_LIMIT_INTERVAL = 60
MAX_RESULTS_PER_REQUEST = 500

INTERVALS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
    "1w": 604800,
}

RATE_LIMITS = [
    RateLimit(limit_id=LIGHTER_LIMIT_ID, limit=LIGHTER_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL),
    RateLimit(
        limit_id=CANDLES_ENDPOINT,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=10)],
    ),
    RateLimit(
        limit_id=ORDER_BOOKS_ENDPOINT,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=10)],
    ),
]


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
        return REST_URL

    @property
    def wss_url(self):
        return WSS_URL

    @property
    def health_check_url(self):
        return REST_URL + ORDER_BOOKS_ENDPOINT

    @property
    def candles_url(self):
        return REST_URL + CANDLES_ENDPOINT

    @property
    def candles_endpoint(self):
        return CANDLES_ENDPOINT

    @property
    def candles_max_result_per_rest_request(self):
        return MAX_RESULTS_PER_REQUEST

    @property
    def rate_limits(self):
        return RATE_LIMITS

    @property
    def intervals(self):
        return INTERVALS

    def get_exchange_trading_pair(self, trading_pair: str) -> str:
        return trading_pair

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url,
            throttler_limit_id=ORDER_BOOKS_ENDPOINT,
            method=RESTMethod.GET,
        )
        return NetworkStatus.CONNECTED

    async def initialize_exchange_data(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=self.health_check_url,
            throttler_limit_id=ORDER_BOOKS_ENDPOINT,
            method=RESTMethod.GET,
        )
        base_asset = self._trading_pair.split("-")[0]
        quote_asset = self._trading_pair.split("-")[1]
        expected_symbol = f"{base_asset}/{quote_asset}"
        for ob in response.get("order_books", []):
            if ob.get("market_type") == "spot" and ob.get("symbol") == expected_symbol:
                self._market_id = ob["market_id"]
                return
        raise ValueError(
            f"Spot market '{expected_symbol}' not found in Lighter order books."
        )

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        params: dict = {
            "market_id": self._market_id,
            "resolution": self.interval,
            "set_timestamp_to_end": "true",
        }
        if start_time is not None:
            params["start_timestamp"] = start_time
        if end_time is not None:
            params["end_timestamp"] = end_time
        params["count_back"] = limit if limit is not None else self.candles_max_result_per_rest_request
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        rows = []
        for candle in data.get("c", []):
            ts = float(candle["t"]) / 1000
            if end_time is not None and ts > end_time:
                continue
            rows.append([
                ts,
                float(candle["o"]),
                float(candle["h"]),
                float(candle["l"]),
                float(candle["c"]),
                float(candle["v"]),
                float(candle["V"]),
                float(candle["i"]),
                0.0,
                0.0,
            ])
        return rows

    def ws_subscription_payload(self) -> dict:
        return {
            "type": "subscribe",
            "channel": f"trade/{self._market_id}",
        }

    def _parse_websocket_message(self, data: dict):
        return None

    async def listen_for_subscriptions(self):
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                seed = await self.fetch_candles(end_time=int(self._time()))
                if len(seed) > 0:
                    for row in seed:
                        self._candles.append(row)
                    self._ws_candle_available.set()
                await self._process_websocket_messages(websocket_assistant=ws)
            except asyncio.CancelledError:
                raise
            except ConnectionError as e:
                self.logger().warning(f"The websocket connection was closed ({e})")
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public klines. Retrying in 1 seconds..."
                )
                await self._sleep(1.0)
            finally:
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _process_websocket_messages_task(self, websocket_assistant: WSAssistant):
        expected_channel = f"trade:{self._market_id}"
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if not isinstance(data, dict):
                continue
            if data.get("channel") != expected_channel:
                continue
            trade_data = data.get("data", {})
            trade_ts = int(trade_data.get("created_at", 0))
            bucket_ts = trade_ts - (trade_ts % self.interval_in_seconds)
            candles = await self.fetch_candles(
                start_time=bucket_ts,
                end_time=bucket_ts + self.interval_in_seconds,
                limit=1,
            )
            if len(candles) == 0:
                continue
            candle_row = candles[0]
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
