import logging
import time
from typing import List, Optional

import pandas as pd

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.kucoin_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class KucoinSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None
    _last_ws_message_sent_timestamp = 0
    _ping_interval = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1min", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)
        self._ws_url = None
        self._ws_token = None

    @property
    def name(self):
        return f"kucoin_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        return f"{self._ws_url}?token={self._ws_token}"

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
    def public_ws_url(self):
        return self.rest_url + CONSTANTS.PUBLIC_WS_DATA_PATH_URL

    @property
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def intervals(self):
        return CONSTANTS.INTERVALS

    @property
    def candles_df(self) -> pd.DataFrame:
        df = pd.DataFrame(self._candles, columns=self.columns, dtype=float)
        return df.sort_values(by="timestamp", ascending=True)

    @property
    def _ping_payload(self):
        return {
            "type": "ping"
        }

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        """
        For API documentation, please refer to:
        https://www.kucoin.com/docs/rest/spot-trading/market-data/get-klines
        """
        params = {"symbol": self._ex_trading_pair, "type": CONSTANTS.INTERVALS[self.interval]}
        if start_time:
            params["startAt"] = start_time
        if end_time:
            params["endAt"] = end_time
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        return [[self.ensure_timestamp_in_seconds(row[0]), row[1], row[3], row[4], row[2], row[5], row[6], 0., 0., 0.]
                for row in data['data']][::-1]

    def ws_subscription_payload(self):
        return {
            "id": str(get_tracking_nonce()),
            "type": "subscribe",
            "topic": f"/market/candles:{self._ex_trading_pair}_{CONSTANTS.INTERVALS[self.interval]}",
            "privateChannel": False,
            "response": False,
        }

    def _parse_websocket_message(self, data: dict):
        candles_row_dict = {}
        if data is not None and data.get(
                "subject") == "trade.candles.update":  # data will be None when the websocket is disconnected
            candles = data["data"]["candles"]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(candles[0])
            candles_row_dict["open"] = candles[1]
            candles_row_dict["close"] = candles[2]
            candles_row_dict["high"] = candles[3]
            candles_row_dict["low"] = candles[4]
            candles_row_dict["volume"] = candles[5]
            candles_row_dict["quote_asset_volume"] = candles[6]
            candles_row_dict["n_trades"] = 0.
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.
            return candles_row_dict

    async def initialize_exchange_data(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        connection_info = await rest_assistant.execute_request(
            url=self.public_ws_url,
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.PUBLIC_WS_DATA_PATH_URL,
        )

        self._ws_url = connection_info["data"]["instanceServers"][0]["endpoint"]
        self._ping_timeout = int(connection_info["data"]["instanceServers"][0]["pingTimeout"]) * 1e-3
        self._ws_token = connection_info["data"]["token"]

    @staticmethod
    def _time():
        return time.time()
