import logging
import time
from typing import List, Optional

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
        return trading_pair.replace("-", "_")

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        """
        For API documentation, please refer to:
        https://www.gate.io/docs/developers/apiv4/en/#market-candlesticks

        This API only accepts a limit of 10000 candles ago.
        """
        if start_time is None:
            start_time = end_time
        if end_time is None:
            end_time = start_time
        candles_ago = (int(time.time()) - start_time) // self.interval_in_seconds
        if candles_ago > CONSTANTS.MAX_CANDLES_AGO:
            raise ValueError("Gate.io REST API does not support fetching more than 10000 candles ago.")
        return {
            "currency_pair": self._ex_trading_pair,
            "interval": self.interval,
            "from": start_time,
            "to": end_time
        }

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        new_hb_candles = []
        for i in data:
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
        return new_hb_candles

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
            candles_row_dict["volume"] = data["result"]["a"]
            candles_row_dict["quote_asset_volume"] = data["result"]["v"]
            candles_row_dict["n_trades"] = 0
            candles_row_dict["taker_buy_base_volume"] = 0
            candles_row_dict["taker_buy_quote_volume"] = 0
            return candles_row_dict
