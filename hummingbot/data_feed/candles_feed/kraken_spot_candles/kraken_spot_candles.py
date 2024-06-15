import logging
import time
from typing import List, Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.kraken_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class KrakenSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 720):
        if max_records > 720:
            raise Exception("Kraken only supports a maximum of 720 records.")
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"kraken_{self._trading_pair}"

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

    @staticmethod
    def convert_to_exchange_symbol(symbol: str) -> str:
        inverted_kraken_to_hb_map = {v: k for k, v in CONSTANTS.KRAKEN_TO_HB_MAP.items()}
        return inverted_kraken_to_hb_map.get(symbol, symbol)

    def get_exchange_trading_pair(self, hb_trading_pair: str, delimiter: str = "") -> str:
        """
        Note: The result of this method can safely be used to submit/make queries.
        Result shouldn't be used to parse responses as Kraken add special formating to most pairs.
        """
        if "-" in hb_trading_pair:
            base, quote = hb_trading_pair.split("-")
        elif "/" in hb_trading_pair:
            base, quote = hb_trading_pair.split("/")
        else:
            return hb_trading_pair
        base = self.convert_to_exchange_symbol(base)
        quote = self.convert_to_exchange_symbol(quote)

        exchange_trading_pair = f"{base}{delimiter}{quote}"
        return exchange_trading_pair

    async def fetch_candles(self,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST):
        """
        Fetches candles data from the exchange.

        - Timestamp must be in seconds
        - The array must be sorted by timestamp in ascending order. Oldest first, newest last.
        - The array must be in the format: [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades,
        taker_buy_base_volume, taker_buy_quote_volume]

        For API documentation, please refer to:
        https://docs.kraken.com/rest/#tag/Spot-Market-Data/operation/getOHLCData

        This endpoint allows you to return up to 3600 candles ago.

        :param start_time: the start time of the candles data to fetch
        :param end_time: the end time of the candles data to fetch
        :param limit: the maximum number of candles to fetch
        :return: the candles data
        """
        if start_time is None:
            start_time = end_time - self.interval_in_seconds * (limit - 1)
        candles_ago = (int(time.time()) - start_time) // self.interval_in_seconds
        if candles_ago > CONSTANTS.MAX_CANDLES_AGO:
            raise ValueError("Kraken REST API does not support fetching more than 720 candles ago.")
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"pair": self._ex_trading_pair, "interval": CONSTANTS.INTERVALS[self.interval], "since": start_time}
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)

        data: List = next(iter(candles["result"].values()))

        new_hb_candles = []
        for i in data:
            timestamp = self.ensure_timestamp_in_seconds(float(i[0])) - self.interval_in_seconds
            open = i[1]
            high = i[2]
            low = i[3]
            close = i[4]
            volume = i[6]
            quote_asset_volume = float(volume) * float(i[5])
            n_trades = 0
            taker_buy_base_volume = 0
            taker_buy_quote_volume = 0
            new_hb_candles.append([timestamp, open, high, low, close, volume,
                                   quote_asset_volume, n_trades, taker_buy_base_volume,
                                   taker_buy_quote_volume])
        return np.array(new_hb_candles).astype(float)

    def ws_subscription_payload(self):
        return {
            "event": "subscribe",
            "pair": [self.get_exchange_trading_pair(self._trading_pair, '/')],
            "subscription": {"name": CONSTANTS.WS_CANDLES_ENDPOINT,
                             "interval": int(CONSTANTS.INTERVALS[self.interval])}
        }

    def _parse_websocket_message(self, data: dict):
        candles_row_dict = {}
        if not (type(data) is dict and "event" in data.keys() and
                data["event"] in ["heartbeat", "systemStatus", "subscriptionStatus"]):
            if data[-2][:4] == "ohlc":
                candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(data[1][1]) - self.interval_in_seconds
                candles_row_dict["open"] = data[1][2]
                candles_row_dict["high"] = data[1][3]
                candles_row_dict["low"] = data[1][4]
                candles_row_dict["close"] = data[1][5]
                candles_row_dict["volume"] = data[1][7]
                candles_row_dict["quote_asset_volume"] = float(data[1][7]) * float(data[1][6])
                candles_row_dict["n_trades"] = 0
                candles_row_dict["taker_buy_base_volume"] = 0
                candles_row_dict["taker_buy_quote_volume"] = 0
                return candles_row_dict
