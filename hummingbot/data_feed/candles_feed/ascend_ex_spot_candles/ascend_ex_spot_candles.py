import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.data_feed.candles_feed.ascend_ex_spot_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class AscendExSpotCandles(CandlesBase):
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
        return f"ascend_ex_{self._trading_pair}"

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
        return trading_pair.replace("-", "/")

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        """
        For API documentation, please refer to:
        https://ascendex.github.io/ascendex-pro-api/#historical-bar-data
        """
        params = {
            "symbol": self._ex_trading_pair,
            "interval": CONSTANTS.INTERVALS[self.interval],
            "n": limit,
        }
        if start_time:
            params["from"] = start_time * 1000
            params["to"] = (start_time + self.interval_in_seconds * limit) * 1000
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        new_hb_candles = []
        for i in data["data"]:
            timestamp = self.ensure_timestamp_in_seconds(i["data"]["ts"])
            if timestamp >= end_time:
                continue
            open = i["data"]["o"]
            high = i["data"]["h"]
            low = i["data"]["l"]
            close = i["data"]["c"]
            quote_asset_volume = i["data"]["v"]
            # no data field
            volume = 0
            n_trades = 0
            taker_buy_base_volume = 0
            taker_buy_quote_volume = 0
            new_hb_candles.append([timestamp, open, high, low, close, volume,
                                   quote_asset_volume, n_trades, taker_buy_base_volume,
                                   taker_buy_quote_volume])
        return new_hb_candles

    def ws_subscription_payload(self):
        payload = {"op": CONSTANTS.SUB_ENDPOINT_NAME,
                   "ch": f"bar:{CONSTANTS.INTERVALS[self.interval]}:{self._ex_trading_pair}"}
        return payload

    def _parse_websocket_message(self, data: dict):
        if data.get("m") == "ping":
            pong_payloads = {"op": "pong"}
            return WSJSONRequest(payload=pong_payloads)
        candles_row_dict: Dict[str, Any] = {}
        if data is not None and data.get("m") == "bar":
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(data["data"]["ts"])
            candles_row_dict["open"] = data["data"]["o"]
            candles_row_dict["low"] = data["data"]["l"]
            candles_row_dict["high"] = data["data"]["h"]
            candles_row_dict["close"] = data["data"]["c"]
            candles_row_dict["volume"] = 0
            candles_row_dict["quote_asset_volume"] = data["data"]["v"]
            candles_row_dict["n_trades"] = 0
            candles_row_dict["taker_buy_base_volume"] = 0
            candles_row_dict["taker_buy_quote_volume"] = 0
            return candles_row_dict
