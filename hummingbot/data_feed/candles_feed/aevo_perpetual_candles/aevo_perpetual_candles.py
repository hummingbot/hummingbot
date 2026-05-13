import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.aevo_perpetual_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class AevoPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)
        self._ping_timeout = CONSTANTS.PING_TIMEOUT
        self._current_ws_candle: Optional[Dict[str, Any]] = None

    async def initialize_exchange_data(self):
        if self._ex_trading_pair is None:
            self._ex_trading_pair = self.get_exchange_trading_pair(self._trading_pair)

    @property
    def name(self):
        return f"aevo_perpetual_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        return CONSTANTS.WSS_URL

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def candles_url(self):
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT

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
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        base_asset = trading_pair.split("-")[0]
        return f"{base_asset}-PERP"

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = None) -> dict:
        if limit is None:
            limit = self.candles_max_result_per_rest_request
            if start_time is not None and end_time is not None:
                expected_records = int((end_time - start_time) / self.interval_in_seconds) + 1
                limit = min(limit, expected_records)

        params = {
            "instrument_name": self._ex_trading_pair,
            "resolution": CONSTANTS.INTERVALS[self.interval],
            "limit": limit,
        }
        if start_time is not None:
            params["start_timestamp"] = int(start_time * 1e9)
        if end_time is not None:
            params["end_timestamp"] = int(end_time * 1e9)
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        history = []
        if data is not None:
            history = data.get("history", [])
        if history:
            candles = []
            for timestamp, price in reversed(history):
                candle_price = float(price)
                candles.append([
                    self.ensure_timestamp_in_seconds(timestamp),
                    candle_price,
                    candle_price,
                    candle_price,
                    candle_price,
                    0.,
                    0.,
                    0.,
                    0.,
                    0.,
                ])
            return candles
        return []

    def ws_subscription_payload(self):
        return {
            "op": "subscribe",
            "data": [f"{CONSTANTS.WS_TICKER_CHANNEL}:{self._ex_trading_pair}"],
        }

    def _parse_websocket_message(self, data):
        if data is None:
            return None
        channel = data.get("channel")
        if channel != f"{CONSTANTS.WS_TICKER_CHANNEL}:{self._ex_trading_pair}":
            return None
        tickers = data.get("data", {}).get("tickers", [])
        if not tickers:
            return None
        ticker = tickers[0]
        price = None
        mark = ticker.get("mark") or {}
        if "price" in mark:
            price = mark["price"]
        elif "index_price" in ticker:
            price = ticker["index_price"]
        if price is None:
            return None
        timestamp = data.get("data", {}).get("timestamp") or data.get("write_ts")
        if timestamp is None:
            return None
        timestamp_s = self.ensure_timestamp_in_seconds(timestamp)
        candle_timestamp = int(timestamp_s - (timestamp_s % self.interval_in_seconds))
        candle_price = float(price)

        if self._current_ws_candle is None or candle_timestamp > self._current_ws_candle["timestamp"]:
            self._current_ws_candle = {
                "timestamp": candle_timestamp,
                "open": candle_price,
                "high": candle_price,
                "low": candle_price,
                "close": candle_price,
                "volume": 0.,
                "quote_asset_volume": 0.,
                "n_trades": 0.,
                "taker_buy_base_volume": 0.,
                "taker_buy_quote_volume": 0.,
            }
        elif candle_timestamp == self._current_ws_candle["timestamp"]:
            self._current_ws_candle["high"] = max(self._current_ws_candle["high"], candle_price)
            self._current_ws_candle["low"] = min(self._current_ws_candle["low"], candle_price)
            self._current_ws_candle["close"] = candle_price
        else:
            return None

        return self._current_ws_candle

    @property
    def _ping_payload(self):
        return CONSTANTS.PING_PAYLOAD
