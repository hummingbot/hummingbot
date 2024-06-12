import logging
import time
from typing import Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.gate_io_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class GateioPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)
        self.quanto_multiplier = None

    @property
    def name(self):
        return f"gate_io_perpetual_{self._trading_pair}"

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

    async def initialize_exchange_data(self):
        await self.get_exchange_trading_pair_quanto_multiplier()

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "_")

    async def get_exchange_trading_pair_quanto_multiplier(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=self.rest_url + CONSTANTS.CONTRACT_INFO_URL.format(contract=self._ex_trading_pair),
            throttler_limit_id=CONSTANTS.CONTRACT_INFO_URL
        )
        quanto_multiplier = float(data.get("quanto_multiplier"))
        self.quanto_multiplier = quanto_multiplier
        return quanto_multiplier

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
            https://www.gate.io/docs/developers/apiv4/#get-futures-candlesticks

            :param start_time: the start time of the candles data to fetch
            :param end_time: the end time of the candles data to fetch
            :param limit: the maximum number of candles to fetch
            :return: the candles data
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {
            "contract": self._ex_trading_pair,
            "interval": self.interval,
            "from": start_time if start_time is not None else end_time - limit * self.interval_in_seconds,
            "to": end_time if end_time is not None else start_time + limit * self.interval_in_seconds
        }

        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)
        new_hb_candles = []
        for i in candles:
            timestamp = i.get("t")
            open = i.get("o")
            high = i.get("h")
            low = i.get("l")
            close = i.get("c")
            volume = i.get("v") * self.quanto_multiplier
            quote_asset_volume = i.get("sum")
            n_trades = 0
            taker_buy_base_volume = 0
            taker_buy_quote_volume = 0
            new_hb_candles.append([self.ensure_timestamp_in_seconds(timestamp), open, high, low, close, volume,
                                   quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume])
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
        if data.get("event") == "update" and data.get("channel") == "futures.candlesticks":
            for i in data["result"]:
                candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(i["t"])
                candles_row_dict["open"] = i["o"]
                candles_row_dict["high"] = i["h"]
                candles_row_dict["low"] = i["l"]
                candles_row_dict["close"] = i["c"]
                candles_row_dict["volume"] = i["v"] * self.quanto_multiplier
                candles_row_dict["quote_asset_volume"] = i.get("sum", 0)
                candles_row_dict["n_trades"] = 0
                candles_row_dict["taker_buy_base_volume"] = 0
                candles_row_dict["taker_buy_quote_volume"] = 0
            return candles_row_dict
