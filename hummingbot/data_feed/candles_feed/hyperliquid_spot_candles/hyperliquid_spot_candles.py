import asyncio
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.hyperliquid_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class HyperliquidSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        self._universe = None
        self._coins_dict = None
        self._base_asset = trading_pair.split("-")[0]
        self._universe_ready = asyncio.Event()
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"hyperliquid_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        return CONSTANTS.WSS_URL

    @property
    def health_check_url(self):
        return self.rest_url

    @property
    def candles_url(self):
        return self.rest_url

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
        await rest_assistant.execute_request(url=self.rest_url,
                                             method=RESTMethod.POST,
                                             throttler_limit_id=self.rest_url,
                                             data=CONSTANTS.HEALTH_CHECK_PAYLOAD)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "")

    async def fetch_candles(self, start_time: Optional[int] = None, end_time: Optional[int] = None,
                            limit: Optional[int] = None) -> List[List[float]]:
        if start_time is None and end_time is None:
            raise ValueError("Either the start time or end time must be specified.")

        if limit is None:
            limit = self.candles_max_result_per_rest_request - 1
        candles_to_fetch = min(self.candles_max_result_per_rest_request - 1, limit)

        reqs = {
            "interval": CONSTANTS.INTERVALS[self.interval],
            "coin": self._coins_dict[self._base_asset],
        }
        if start_time:
            reqs["startTime"] = start_time * 1000
        else:
            reqs["startTime"] = (end_time - candles_to_fetch * self.interval_in_seconds) * 1000
        payload = {
            "type": "candleSnapshot",
            "req": reqs
        }
        headers = self._get_rest_candles_headers()
        rest_assistant = await self._api_factory.get_rest_assistant()
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=self.rest_url,
                                                       data=payload,
                                                       headers=headers,
                                                       method=RESTMethod.POST)
        arr = self._parse_rest_candles(candles, end_time)
        return np.array(arr).astype(float)

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = None) -> dict:
        pass

    def _get_rest_candles_headers(self):
        return {"Content-Type": "application/json"}

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        if len(data) > 0:
            return [
                [self.ensure_timestamp_in_seconds(row["t"]), row["o"], row["h"], row["l"], row["c"], row["v"], 0.,
                 row["n"], 0., 0.] for row in data if self.ensure_timestamp_in_seconds(row["t"]) < end_time
            ]

    def ws_subscription_payload(self):
        interval = CONSTANTS.INTERVALS[self.interval]
        payload = {
            "method": "subscribe",
            "subscription": {
                "type": "candle",
                "coin": self._coins_dict[self._base_asset],
                "interval": interval
            },
        }
        return payload

    def _parse_websocket_message(self, data):
        candles_row_dict: Dict[str, Any] = {}
        if data is not None and data.get("channel") == "candle":
            candle = data["data"]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(candle["t"])
            candles_row_dict["open"] = candle["o"]
            candles_row_dict["low"] = candle["l"]
            candles_row_dict["high"] = candle["h"]
            candles_row_dict["close"] = candle["c"]
            candles_row_dict["volume"] = candle["v"]
            candles_row_dict["quote_asset_volume"] = 0.
            candles_row_dict["n_trades"] = candle["n"]
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.
            return candles_row_dict

    async def initialize_exchange_data(self):
        await self._initialize_coins_dict()

    async def _initialize_coins_dict(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        self._universe = await rest_assistant.execute_request(url=self.rest_url,
                                                              method=RESTMethod.POST,
                                                              throttler_limit_id=self.rest_url,
                                                              data=CONSTANTS.HEALTH_CHECK_PAYLOAD)
        universe = {token["tokens"][0]: token["name"] for token in self._universe["universe"]}
        tokens = {token["index"]: token["name"] for token in self._universe["tokens"]}
        self._coins_dict = {tokens[index]: universe[index] for index in universe.keys()}
