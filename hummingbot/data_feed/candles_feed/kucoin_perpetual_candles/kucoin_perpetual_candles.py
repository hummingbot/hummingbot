import logging
import time
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
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

    def __init__(self,
                 trading_pair: str,
                 interval: str = "1min",
                 max_records: int = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST):
        self.symbols_dict = {}
        super().__init__(trading_pair, interval, max_records)
        self.hb_base_asset = self._trading_pair.split("-")[0]
        self.kucoin_base_asset = self.get_kucoin_base_asset()
        self.quote_asset = self._trading_pair.split("-")[1]

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
        return CONSTANTS.WSS_URL

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def candles_url(self):
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT

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

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    @property
    def symbols_url(self):
        return self.rest_url + CONSTANTS.SYMBOLS_ENDPOINT

    async def generate_symbols_dict(self) -> Dict[str, Any]:
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

    def get_exchange_trading_pair(self, trading_pair):
        return f"{self.kucoin_base_asset}-{self.quote_asset}" if bool(self.symbols_dict) else None

    async def symbols_ready(self):
        while not bool(self.symbols_dict):
            await self.generate_symbols_dict()
            self._ex_trading_pair = self.get_exchange_trading_pair(self._trading_pair)
        return bool(self._ex_trading_pair)

    async def fetch_candles(self, start_time: Optional[int] = None, end_time: Optional[int] = None,
                            limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST):
        """
        Fetches candles data from the exchange.

        - Timestamp must be in seconds
        - The array must be sorted by timestamp in ascending order. Oldest first, newest last.
        - The array must be in the format: [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume]

        For API documentation, please refer to:
        https://www.kucoin.com/docs/rest/futures-trading/market-data/get-klines

        :param start_time: the start time of the candles data to fetch
        :param end_time: the end time of the candles data to fetch
        :param limit: the maximum number of candles to fetch
        :return: the candles data
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        await self.symbols_ready()
        params = {
            "symbol": self.symbols_dict[f"{self.kucoin_base_asset}-{self.quote_asset}"],
            "granularity": CONSTANTS.GRANULARITIES[self.interval],
        }
        if start_time:
            params["from"] = start_time * 1000

        response = await rest_assistant.execute_request(url=self.candles_url,
                                                        throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                        params=params)
        candles = np.array([[self.ensure_timestamp_in_seconds(row[0]), row[1], row[2], row[3], row[4], row[5],
                             0., 0., 0., 0.]
                            for row in response['data']]
                           ).astype(float)
        return candles

    def ws_subscription_payload(self):
        if not bool(self.symbols_dict):
            self._sleep(1)
            return
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
        if "candles" in data:
            candles = data["candles"]
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

    async def _connected_websocket_assistant(self) -> WSAssistant:
        rest_assistant = await self._api_factory.get_rest_assistant()
        connection_info = await rest_assistant.execute_request(
            url=self.public_ws_url,
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.PUBLIC_WS_DATA_PATH_URL,
        )

        ws_url = connection_info["data"]["instanceServers"][0]["endpoint"]
        self._ping_interval = int(connection_info["data"]["instanceServers"][0]["pingInterval"]) * 0.8 * 1e-3
        token = connection_info["data"]["token"]

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=f"{ws_url}?token={token}", message_timeout=self._ping_interval)
        return ws

    def _time(self):
        return time.time()
