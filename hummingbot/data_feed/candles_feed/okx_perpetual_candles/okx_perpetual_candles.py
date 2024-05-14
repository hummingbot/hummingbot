import asyncio
import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig
from hummingbot.data_feed.candles_feed.okx_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class OKXPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m",
                 max_records: int = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST):
        super().__init__(trading_pair, interval, max_records)
        self.interval_to_milliseconds_dict = {
            "1s": 1000,
            "1m": 60000,
            "3m": 180000,
            "5m": 300000,
            "15m": 900000,
            "30m": 1800000,
            "1h": 3600000,
            "2h": 7200000,
            "4h": 14400000,
            "6h": 21600000,
            "8h": 28800000,
            "12h": 43200000,
            "1d": 86400000,
            "3d": 259200000,
            "1w": 604800000,
            "1M": 2592000000,
            "3M": 7776000000
        }

    @property
    def name(self):
        return f"okx_perpetual_{self._trading_pair}"

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

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return f"{trading_pair}-SWAP"

    async def fetch_candles(self,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit: Optional[int] = 100):
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"instId": self._ex_trading_pair, "bar": CONSTANTS.INTERVALS[self.interval], "limit": limit}
        if end_time:
            params["after"] = end_time
        if start_time:
            params["before"] = start_time
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)

        arr = [[row[0], row[1], row[2], row[3], row[4], row[6], row[7], 0., 0., 0.] for row in candles["data"]]
        return np.array(arr).astype(float)

    async def fill_historical_candles(self):
        max_request_needed = (self._candles.maxlen // CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) + 1
        requests_executed = 0
        while not self.ready:
            missing_records = self._candles.maxlen - len(self._candles)
            end_timestamp = int(self._candles[0][0])
            try:
                if requests_executed < max_request_needed:
                    # we have to add one more since, the last row is not going to be included
                    candles = await self.fetch_candles(end_time=end_timestamp, limit=missing_records + 1)
                    # we are computing again the quantity of records again since the websocket process is able to
                    # modify the deque and if we extend it, the new observations are going to be dropped.
                    missing_records = self._candles.maxlen - len(self._candles)
                    self._candles.extendleft(candles[-(missing_records + 1):-1])
                    requests_executed += 1
                else:
                    self.logger().error(f"There is no data available for the quantity of "
                                        f"candles requested for {self.name}.")
                    raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when getting historical klines. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)

    async def get_historical_candles(self, config: HistoricalCandlesConfig):
        try:
            all_candles = []
            current_start_time = config.start_time
            while current_start_time <= config.end_time:
                current_end_time = current_start_time + self.interval_to_milliseconds_dict[config.interval] * CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST
                fetched_candles = await self.fetch_candles(end_time=current_end_time)
                if fetched_candles.size == 0:
                    break

                all_candles.append(fetched_candles[::-1])
                last_timestamp = fetched_candles[0][0]  # Assuming the first column is the timestamp
                current_start_time = int(last_timestamp)

            final_candles = np.concatenate(all_candles, axis=0) if all_candles else np.array([])
            candles_df = pd.DataFrame(final_candles, columns=self.columns)
            candles_df.drop_duplicates(subset=["timestamp"], inplace=True)
            return candles_df
        except Exception as e:
            self.logger().exception(f"Error fetching historical candles: {str(e)}")

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            candle_args = []
            candle_args.append({"channel": f"candle{CONSTANTS.INTERVALS[self.interval]}", "instId": self._ex_trading_pair})
            payload = {
                "op": "subscribe",
                "args": candle_args
            }
            subscribe_candles_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_candles_request)
            self.logger().info("Subscribed to public klines...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to public klines...",
                exc_info=True
            )
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data
            if data is not None and "data" in data:  # data will be None when the websocket is disconnected
                candles = data["data"][0]
                timestamp = candles[0]
                open = candles[1]
                high = candles[2]
                low = candles[3]
                close = candles[4]
                volume = candles[6]
                quote_asset_volume = candles[7]
                n_trades = 0.
                taker_buy_base_volume = 0.
                taker_buy_quote_volume = 0.

                candles_row = np.array([timestamp, open, high, low, close, volume,
                                        quote_asset_volume, n_trades, taker_buy_base_volume,
                                        taker_buy_quote_volume]).astype(float)
                if len(self._candles) == 0:
                    self._candles.append(candles_row)
                    safe_ensure_future(self.fill_historical_candles())
                elif int(timestamp) > int(self._candles[-1][0]):
                    self._candles.append(candles_row)
                elif int(timestamp) == int(self._candles[-1][0]):
                    self._candles.pop()
                    self._candles.append(candles_row)
