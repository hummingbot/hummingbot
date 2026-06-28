import logging
from typing import List, Optional

import pandas as pd

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.backpack_spot_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class BackpackSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"backpack_{self._trading_pair}"

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

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return True

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "_")

    @staticmethod
    def _iso_to_seconds(iso_timestamp: str) -> int:
        """Backpack returns candle boundaries as UTC ISO-8601 strings (e.g. "2024-01-01T00:00:00")."""
        return int(pd.Timestamp(iso_timestamp, tz="UTC").timestamp())

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        # Backpack expects startTime/endTime in seconds and requires startTime to be present.
        params = {
            "symbol": self._ex_trading_pair,
            "interval": self.intervals[self.interval],
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return params

    def _parse_rest_candles(self, data: list, end_time: Optional[int] = None) -> List[List[float]]:
        # Backpack does not report taker buy volumes, so those columns are filled with 0.
        return [
            [self._iso_to_seconds(row["start"]),
             row["open"], row["high"], row["low"], row["close"], row["volume"],
             row["quoteVolume"], row["trades"], 0., 0.]
            for row in data
            if row["open"] is not None
        ]

    def ws_subscription_payload(self):
        candle_params = [f"kline.{self.intervals[self.interval]}.{self._ex_trading_pair}"]
        payload = {
            "method": "SUBSCRIBE",
            "params": candle_params,
        }
        return payload

    def _parse_websocket_message(self, data: dict):
        candles_row_dict = {}
        if data is not None and data.get("data", {}).get("e") == "kline":
            kline = data["data"]
            # Empty buckets (no trades yet) arrive with null OHLC; skip them.
            if kline.get("o") is None:
                return None
            candles_row_dict["timestamp"] = self._iso_to_seconds(kline["t"])
            candles_row_dict["open"] = kline["o"]
            candles_row_dict["high"] = kline["h"]
            candles_row_dict["low"] = kline["l"]
            candles_row_dict["close"] = kline["c"]
            candles_row_dict["volume"] = kline["v"]
            # Backpack's kline websocket stream does not include quote volume (the REST endpoint
            # does). As a live approximation we use base_volume * close; this differs slightly from
            # the true traded quote volume (VWAP-based) and is overwritten by the exact REST value
            # on the next historical backfill.
            # TODO(backpack): request that the kline WS stream include quoteVolume like the REST API.
            candles_row_dict["quote_asset_volume"] = float(kline["v"]) * float(kline["c"])
            candles_row_dict["n_trades"] = kline["n"]
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.
            return candles_row_dict
