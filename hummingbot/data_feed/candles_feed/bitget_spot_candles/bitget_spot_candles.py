import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.bitget_spot_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class BitgetSpotCandles(CandlesBase):
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
        return f"bitget_{self._trading_pair}"

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
        await rest_assistant.execute_request(
            url=self.health_check_url,
            throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT
        )

        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "")

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_last_candle_not_in_rest_request(self):
        return False

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST
    ) -> dict:

        params = {
            "symbol": self._ex_trading_pair,
            "granularity": CONSTANTS.INTERVALS[self.interval],
            "limit": limit
        }
        if start_time is not None:
            params["startTime"] = start_time * 1000
        if end_time is not None:
            params["endTime"] = end_time * 1000

        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        """
        Rest response example:
        {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695865615662,
            "data": [
                [
                    "1695835800000",  # Timestamp ms
                    "26210.5",        # Opening
                    "26210.5",        # Highest
                    "26194.5",        # Lowest
                    "26194.5",        # Closing
                    "26.26",          # Volume base
                    "687897.63"       # Volume USDT
                    "687897.63"       # Volume quote
                ]
            ]
        }
        """
        if data is not None and data.get("data") is not None:
            candles = data["data"]

            return [
                [
                    self.ensure_timestamp_in_seconds(int(row[0])),
                    float(row[1]), float(row[2]), float(row[3]),
                    float(row[4]), float(row[5]), float(row[7]),
                    0., 0., 0.
                ]
                for row in candles
            ][::-1]

    def ws_subscription_payload(self):
        interval = CONSTANTS.WS_INTERVALS[self.interval]
        channel = f"{CONSTANTS.WS_CANDLES_ENDPOINT}{interval}"
        payload = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "SPOT",
                    "channel": channel,
                    "instId": self._ex_trading_pair
                }
            ]
        }

        return payload

    def _parse_websocket_message(self, data: dict) -> Optional[Dict[str, Any]]:
        """
        WS response example:
        {
            "action": "snapshot",  # or "update"
            "arg": {
                "instType": "SPOT",
                "channel": "candle1m",
                "instId": "ETHUSDT"
            },
            "data": [
                [
                    "1695835800000",  # Timestamp ms
                    "26210.5",        # Opening
                    "26210.5",        # Highest
                    "26194.5",        # Lowest
                    "26194.5",        # Closing
                    "26.26",          # Volume base
                    "687897.63"       # Volume quote
                    "687897.63"       # Volume USDT
                ]
            ],
            "ts": 1695702747821
            }
        """
        candles_row_dict: Dict[str, Any] = {}

        if data is not None and data.get("data") is not None:
            candle = data["data"][0]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(int(candle[0]))
            candles_row_dict["open"] = float(candle[1])
            candles_row_dict["high"] = float(candle[2])
            candles_row_dict["low"] = float(candle[3])
            candles_row_dict["close"] = float(candle[4])
            candles_row_dict["volume"] = float(candle[5])
            candles_row_dict["quote_asset_volume"] = float(candle[6])
            candles_row_dict["n_trades"] = 0.
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.

            return candles_row_dict
