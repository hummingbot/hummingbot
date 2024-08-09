import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.mexc_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class MexcSpotCandles(CandlesBase):
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
        return f"mexc_{self._trading_pair}"

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
        return trading_pair.replace("-", "")

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        """
        For API documentation, please refer to:
        https://mexcdevelop.github.io/apidocs/spot_v3_en/#kline-candlestick-data

        startTime and endTime must be used at the same time.
        """
        params = {
            "symbol": self._ex_trading_pair,
            "interval": CONSTANTS.INTERVALS[self.interval],
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time * 1000
        if end_time:
            params["endTime"] = end_time * 1000
        return params

    def _get_rest_candles_headers(self):
        return {"Content-Type": "application/json"}

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        return [
            [self.ensure_timestamp_in_seconds(row[0]), row[1], row[2], row[3], row[4], row[5], row[7],
             0., 0., 0.]
            for row in data if self.ensure_timestamp_in_seconds(row[0]) < end_time]

    def ws_subscription_payload(self):
        trading_pair = self.get_exchange_trading_pair(self._trading_pair)
        interval = CONSTANTS.WS_INTERVALS[self.interval]
        candle_params = [f"spot@public.kline.v3.api@{trading_pair}@{interval}"]
        payload = {
            "method": "SUBSCRIPTION",
            "params": candle_params,
        }
        return payload

    def _parse_websocket_message(self, data):
        candles_row_dict: Dict[str, Any] = {}
        if data is not None and data.get("d") is not None:
            candle = data["d"]["k"]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(candle["t"])
            candles_row_dict["open"] = candle["o"]
            candles_row_dict["low"] = candle["l"]
            candles_row_dict["high"] = candle["h"]
            candles_row_dict["close"] = candle["c"]
            candles_row_dict["volume"] = candle["v"]
            candles_row_dict["quote_asset_volume"] = 0.
            candles_row_dict["n_trades"] = 0.
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.
            return candles_row_dict
