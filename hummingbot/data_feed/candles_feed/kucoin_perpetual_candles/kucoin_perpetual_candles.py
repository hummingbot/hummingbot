import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.kucoin_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class KucoinPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None
    _last_ws_message_sent_timestamp = 0
    _ping_interval = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        self.symbols_dict = {}
        self.hb_base_asset = trading_pair.split("-")[0]
        self.quote_asset = trading_pair.split("-")[1]
        self.kucoin_base_asset = self.get_kucoin_base_asset()
        super().__init__(trading_pair, interval, max_records)

    def get_kucoin_base_asset(self):
        for hb_asset, kucoin_value in CONSTANTS.HB_TO_KUCOIN_MAP.items():
            return kucoin_value if hb_asset == self.hb_base_asset else self.hb_base_asset

    @property
    def name(self):
        return f"kucoin_perpetual_{self._trading_pair}"

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
    def symbols_url(self):
        return self.rest_url + CONSTANTS.SYMBOLS_ENDPOINT

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
            "type": "ping",
        }

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return f"{self.kucoin_base_asset}-{self.quote_asset}"

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = None) -> dict:
        """
        For API documentation, please refer to:
        https://www.kucoin.com/docs/rest/futures-trading/market-data/get-klines
        """
        granularity = CONSTANTS.GRANULARITIES[self.interval]
        now = self._round_timestamp_to_interval_multiple(self._time())
        granularity_limits = {
            1: 24,  # 1 minute granularity, 24 hours
            5: 10 * 24,  # 5 minutes granularity, 10 days
            15: 30 * 24,  # 15 minutes granularity, 30 days
            30: 60 * 24,  # 30 minutes granularity, 60 days
            60: 120 * 24,  # 1 hour granularity, 120 days
            120: 240 * 24,  # 2 hours granularity, 240 days
            240: 480 * 24,  # 4 hours granularity, 480 days
            480: 720 * 24  # 6 hours granularity, 720 days
        }
        if granularity in granularity_limits:
            max_duration = granularity_limits[granularity] * 60  # convert days to minutes
            if (now - start_time) / 60 >= max_duration:
                raise ValueError(
                    f"{granularity}m granularity candles are only available for the last {granularity_limits[granularity] // 24} days.")

        params = {
            "symbol": self.symbols_dict[f"{self.kucoin_base_asset}-{self.quote_asset}"],
            "granularity": CONSTANTS.GRANULARITIES[self.interval],
            "to": end_time * 1000,
        }
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        return [[self.ensure_timestamp_in_seconds(row[0]), row[1], row[2], row[3], row[4], row[5], 0., 0., 0., 0.]
                for row in data['data']]

    def ws_subscription_payload(self):
        topic_candle = f"{self.symbols_dict[self._ex_trading_pair]}_{CONSTANTS.INTERVALS[self.interval]}"
        payload = {
            "id": str(get_tracking_nonce()),
            "type": "subscribe",
            "topic": f"/contractMarket/limitCandle:{topic_candle}",
            "privateChannel": False,
            "response": True,
        }
        return payload

    def _parse_websocket_message(self, data: dict):
        candles_row_dict: Dict[str, Any] = {}
        if data.get("data") is not None:
            if "candles" in data["data"]:
                candles = data["data"]["candles"]
                candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(int(candles[0]))
                candles_row_dict["open"] = candles[1]
                candles_row_dict["close"] = candles[2]
                candles_row_dict["high"] = candles[3]
                candles_row_dict["low"] = candles[4]
                candles_row_dict["volume"] = candles[5]
                candles_row_dict["quote_asset_volume"] = 0.
                candles_row_dict["n_trades"] = 0.
                candles_row_dict["taker_buy_base_volume"] = 0.
                candles_row_dict["taker_buy_quote_volume"] = 0.
                return candles_row_dict

    async def initialize_exchange_data(self) -> Dict[str, Any]:
        await self._get_symbols_dict()
        await self._get_ws_token()

    async def _get_symbols_dict(self):
        try:
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(url=self.symbols_url,
                                                            throttler_limit_id=CONSTANTS.SYMBOLS_ENDPOINT)
            symbols = response["data"]
            symbols_dict = {}
            for symbol in symbols:
                symbols_dict[f"{symbol['baseCurrency']}-{symbol['quoteCurrency']}"] = symbol["symbol"]
            self.symbols_dict = symbols_dict
        except Exception:
            self.logger().error("Error fetching symbols from Kucoin.")
            raise

    async def _get_ws_token(self):
        try:
            rest_assistant = await self._api_factory.get_rest_assistant()
            connection_info = await rest_assistant.execute_request(
                url=self.public_ws_url,
                method=RESTMethod.POST,
                throttler_limit_id=CONSTANTS.PUBLIC_WS_DATA_PATH_URL,
            )

            self._ws_url = connection_info["data"]["instanceServers"][0]["endpoint"]
            self._ping_timeout = int(connection_info["data"]["instanceServers"][0]["pingTimeout"]) * 1e-3
            self._ws_token = connection_info["data"]["token"]
        except Exception:
            self.logger().error("Error fetching WS token from Kucoin.")
            raise
