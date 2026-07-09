import logging
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as GRVT_CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.grvt_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class GrvtPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)
        self._api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(
            throttler=AsyncThrottler(rate_limits=self.rate_limits)
        )
        self._ping_timeout = GRVT_CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        self._ws_request_id = 0

    @property
    def name(self):
        return f"grvt_perpetual_{self._trading_pair}"

    @property
    def rest_url(self):
        return web_utils.public_rest_url(path_url="").rstrip("/")

    @property
    def wss_url(self):
        return web_utils.public_wss_url()

    @property
    def health_check_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.HEALTH_CHECK_ENDPOINT)

    @property
    def candles_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.CANDLES_ENDPOINT)

    @property
    def candles_endpoint(self):
        return CONSTANTS.CANDLES_ENDPOINT

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
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT,
            data={"kind": ["PERPETUAL"], "limit": 1},
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "_") + "_Perp"

    def _rest_payload(self, **kwargs):
        limit = kwargs["limit"]
        if kwargs.get("end_time") is not None:
            limit += 1
        limit = min(limit, self.candles_max_result_per_rest_request)
        return {
            "instrument": self._ex_trading_pair,
            "interval": CONSTANTS.INTERVALS[self.interval],
            "type": "TRADE",
            "start_time": str(int(kwargs["start_time"] * 1e9)),
            "end_time": str(int(kwargs["end_time"] * 1e9)),
            "limit": limit,
        }

    @property
    def _rest_method(self):
        return RESTMethod.POST

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        return {}

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        candles = sorted(data.get("result", []), key=lambda row: int(row["open_time"]))
        return [
            [
                self.ensure_timestamp_in_seconds(row["open_time"]),
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume_b"],
                row["volume_q"],
                row["trades"],
                0.0,
                0.0,
            ]
            for row in candles
        ]

    def ws_subscription_payload(self):
        self._ws_request_id += 1
        return {
            "jsonrpc": "2.0",
            "method": "subscribe",
            "params": {
                "stream": CONSTANTS.WS_CANDLES_ENDPOINT,
                "selectors": [f"{self._ex_trading_pair}@{CONSTANTS.INTERVALS[self.interval]}-TRADE"],
            },
            "id": self._ws_request_id,
        }

    def _parse_websocket_message(self, data: dict) -> Optional[Dict[str, Any]]:
        if data.get("stream") != CONSTANTS.WS_CANDLES_ENDPOINT or "feed" not in data:
            return None

        candle = data["feed"]
        return {
            "timestamp": self.ensure_timestamp_in_seconds(candle["open_time"]),
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume_b"],
            "quote_asset_volume": candle["volume_q"],
            "n_trades": candle["trades"],
            "taker_buy_base_volume": 0.0,
            "taker_buy_quote_volume": 0.0,
        }
