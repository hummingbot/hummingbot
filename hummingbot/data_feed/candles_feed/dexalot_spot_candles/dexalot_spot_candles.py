import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.dexalot_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class DexalotSpotCandles(CandlesBase):
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
        return f"dexalot_{self._trading_pair}"

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

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return False

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        """
        For API documentation, please refer to:

        startTime and endTime must be used at the same time.
        """
        _intervalstr = self.interval[-1]
        if _intervalstr == 'm':
            intervalstr = 'minute'
        elif _intervalstr == 'h':
            intervalstr = 'hour'
        elif _intervalstr == 'd':
            intervalstr = 'day'
        else:
            intervalstr = ''
        params = {
            "pair": self._ex_trading_pair,
            "intervalnum": CONSTANTS.INTERVALS[self.interval][1:],
            "intervalstr": intervalstr,
        }
        if start_time is not None or end_time is not None:
            start_time = start_time if start_time is not None else end_time - limit * self.interval_in_seconds
            start_isotime = f"{datetime.fromtimestamp(start_time).isoformat(timespec='milliseconds')}Z"
            params["periodfrom"] = start_isotime
            end_time = end_time if end_time is not None else start_time + limit * self.interval_in_seconds
            end_isotiome = f"{datetime.fromtimestamp(end_time).isoformat(timespec='milliseconds')}Z"
            params["periodto"] = end_isotiome
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        if data is not None and len(data) > 0:
            return [[self.ensure_timestamp_in_seconds(datetime.strptime(row["date"], '%Y-%m-%dT%H:%M:%S.%fZ').timestamp()),
                     row["open"] if row["open"] != 'None' else None,
                     row["high"] if row["high"] != 'None' else None,
                     row["low"] if row["low"] != 'None' else None,
                     row["close"] if row["close"] != 'None' else None,
                     row["volume"] if row["volume"] != 'None' else None,
                     0., 0., 0., 0.] for row in data]

    def ws_subscription_payload(self):
        interval = CONSTANTS.INTERVALS[self.interval]
        trading_pair = self.get_exchange_trading_pair(self._trading_pair)

        payload = {
            "pair": trading_pair,
            "chart": interval,
            "type": "chart-v2-subscribe"
        }
        return payload

    def _parse_websocket_message(self, data):
        candles_row_dict: Dict[str, Any] = {}
        if data is not None and data.get("type") == 'liveCandle':
            candle = data.get("data")[-1]
            timestamp = datetime.strptime(candle["date"], '%Y-%m-%dT%H:%M:%SZ').timestamp()
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(timestamp)
            candles_row_dict["open"] = candle["open"]
            candles_row_dict["low"] = candle["low"]
            candles_row_dict["high"] = candle["high"]
            candles_row_dict["close"] = candle["close"]
            candles_row_dict["volume"] = candle["volume"]
            candles_row_dict["quote_asset_volume"] = 0.
            candles_row_dict["n_trades"] = 0.
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.
            return candles_row_dict
