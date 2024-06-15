import logging
import time
from typing import Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.gate_io_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class GateioSpotCandles(CandlesBase):
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
        return f"gate_io_{self._trading_pair}"

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
        return trading_pair.replace("-", "_")

    async def fetch_candles(self, start_time: Optional[int] = None, end_time: Optional[int] = None,
                            limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST):
        """
            Fetches candles data from the exchange.

            - Timestamp must be in seconds
            - The array must be sorted by timestamp in ascending order. Oldest first, newest last.
            - The array must be in the format: [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades,
            taker_buy_base_volume, taker_buy_quote_volume]

            For API documentation, please refer to:
            https://www.gate.io/docs/developers/apiv4/en/#market-candlesticks

            This API only accepts a limit of 10000 candles ago.

            :param start_time: the start time of the candles data to fetch
            :param end_time: the end time of the candles data to fetch
            :param limit: the maximum number of candles to fetch
            :return: the candles data
        """
        if start_time is None:
            start_time = end_time - (limit - 1) * self.interval_in_seconds
        if end_time is None:
            end_time = start_time + (limit - 1) * self.interval_in_seconds
        candles_ago = (int(time.time()) - start_time) // self.interval_in_seconds
        if candles_ago > CONSTANTS.MAX_CANDLES_AGO:
            raise ValueError("Gate.io REST API does not support fetching more than 10000 candles ago.")
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {
            "currency_pair": self._ex_trading_pair,
            "interval": self.interval,
            "from": start_time,
            "to": end_time
        }
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)
        new_hb_candles = []
        for i in candles:
            timestamp = self.ensure_timestamp_in_seconds(i[0])
            if timestamp == end_time:
                continue
            open = i[5]
            high = i[3]
            low = i[4]
            close = i[2]
            volume = i[6]
            quote_asset_volume = i[1]
            # no data field
            n_trades = 0
            taker_buy_base_volume = 0
            taker_buy_quote_volume = 0
            new_hb_candles.append([timestamp, open, high, low, close, volume,
                                   quote_asset_volume, n_trades, taker_buy_base_volume,
                                   taker_buy_quote_volume])
        return np.array(new_hb_candles).astype(float)

    def ws_subscription_payload(self):
        return {
            "time": int(time.time()),
            "channel": CONSTANTS.WS_CANDLES_ENDPOINT,
            "event": "subscribe",
            "payload": [self.interval, self._ex_trading_pair]
        }

    def _parse_websocket_message(self, data: dict):
        candles_row_dict = {}
        if data.get("event") == "update" and data.get("channel") == "spot.candlesticks":
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(data["result"]["t"])
            candles_row_dict["open"] = data["result"]["o"]
            candles_row_dict["high"] = data["result"]["h"]
            candles_row_dict["low"] = data["result"]["l"]
            candles_row_dict["close"] = data["result"]["c"]
            candles_row_dict["volume"] = data["result"]["v"]
            candles_row_dict["quote_asset_volume"] = data["result"]["a"]
            candles_row_dict["n_trades"] = 0
            candles_row_dict["taker_buy_base_volume"] = 0
            candles_row_dict["taker_buy_quote_volume"] = 0
            return candles_row_dict
