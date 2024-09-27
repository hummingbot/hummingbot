import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.binance_perpetual_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class BinancePerpetualCandles(CandlesBase):
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
        return f"binance_perpetual_{self._trading_pair}"

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

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        """
        For API documentation, please refer to:
        https://binance-docs.github.io/apidocs/futures/en/#kline-candlestick-data
        """
        params = {
            "symbol": self._ex_trading_pair,
            "interval": self.interval,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time * 1000
        if end_time:
            params["endTime"] = end_time * 1000
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        return [
            [self.ensure_timestamp_in_seconds(row[0]), row[1], row[2], row[3], row[4], row[5], row[7],
             row[8], row[9], row[10]]
            for row in data
        ]

    def ws_subscription_payload(self):
        candle_params = [f"{self._ex_trading_pair.lower()}@kline_{self.interval}"]
        payload = {
            "method": "SUBSCRIBE",
            "params": candle_params,
            "id": 1
        }
        return payload

    def _parse_websocket_message(self, data):
        candles_row_dict: Dict[str, Any] = {}
        if data is not None and data.get("e") == "kline":  # data will be None when the websocket is disconnected
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(data["k"]["t"])
            candles_row_dict["open"] = data["k"]["o"]
            candles_row_dict["low"] = data["k"]["l"]
            candles_row_dict["high"] = data["k"]["h"]
            candles_row_dict["close"] = data["k"]["c"]
            candles_row_dict["volume"] = data["k"]["v"]
            candles_row_dict["quote_asset_volume"] = data["k"]["q"]
            candles_row_dict["n_trades"] = data["k"]["n"]
            candles_row_dict["taker_buy_base_volume"] = data["k"]["V"]
            candles_row_dict["taker_buy_quote_volume"] = data["k"]["Q"]
            return candles_row_dict
