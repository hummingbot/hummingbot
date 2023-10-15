import asyncio
import logging
from datetime import datetime
from time import time
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class CoinbaseAdvancedTradeSpotCandles(CandlesBase):
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
        return f"coinbase_advanced_trade_{self._trading_pair}"

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
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT.format(product_id=self._ex_trading_pair)

    @property
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def intervals(self):
        return CONSTANTS.INTERVALS

    @property
    def candle_keys_order(self):
        return ["start", "open", "high", "low", "close", "volume"]

    @property
    def candles_df(self) -> pd.DataFrame:
        df = pd.DataFrame(self._candles, columns=["timestamp"] + self.candle_keys_order[1:], dtype=float)
        df = df.reindex(columns=self.columns, fill_value=0.0)
        df["timestamp"] = df["timestamp"] * 1000
        return df.sort_values(by="timestamp", ascending=True)

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "-")

    async def fetch_candles(
            self,
            start_time: int | None = None,
            end_time: int | None = None,
            limit: int | None = 500,
            granularity: str | None = "1m"):
        """
        Fetches candles from the exchange.
        :param start_time: the start time of the candles to be fetched
        :param end_time: the end time of the candles to be fetched
        :param limit: the quantity of candles to be fetched
        :param granularity: the granularity of the candles to be fetched
        :return: a numpy array with the candles
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getcandles
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"granularity": CONSTANTS.INTERVALS[granularity],
                  "start": str(start_time) or str(int(datetime(2023, 1, 1).timestamp())),
                  "end": str(end_time) or str(time())}
        data = await rest_assistant.execute_request(
            url=self.candles_url,
            throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT_ID,
            params=params)

        return np.array(
            [
                [float(candle[key]) for key in self.candle_keys_order]
                for candle in data["candles"]
            ]
        )

    async def fill_historical_candles(self):
        max_request_needed = (self._candles.maxlen // 1000) + 1
        requests_executed = 0
        while not self.is_ready:
            missing_records = self._candles.maxlen - len(self._candles)
            end_timestamp = int(self._candles[0][0])
            try:
                if requests_executed < max_request_needed:
                    # we have to add one more since, the last row is not going to be included
                    candles = await self.fetch_candles(end_time=end_timestamp, limit=missing_records + 1)
                    # we are computing again the quantity of records again since the websocket process is able to
                    # modify the deque and if we extend it, the new observations are going to be dropped.
                    missing_records = self._candles.maxlen - len(self._candles)
                    self._candles.extendleft(candles[-(missing_records + 1):-1][::-1])
                    requests_executed += 1
                else:
                    self.logger().error(f"There is no data available for the quantity of "
                                        f"candles requested for {self.name}.")
                    raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when getting historical candles. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            payload = {
                "type": "subscribe",
                "product_ids": [self._ex_trading_pair],
                "channel": "candles",
            }
            subscribe_candles_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_candles_request)
            self.logger().info("Subscribed to public candles...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to public candles...",
                exc_info=True
            )
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data
            if data is not None and data.get(
                    "channel") == "candles":  # data will be None when the websocket is disconnected
                for event in data["events"]:
                    for candle in event["candles"]:
                        candle = np.array([float(candle[key]) for key in self.candle_keys_order])

                        if len(self._candles) == 0:
                            self._candles.append(candle)
                            safe_ensure_future(self.fill_historical_candles())

                        elif candle[0] > int(self._candles[-1][0]):
                            # TODO: validate also that the diff of timestamp == interval (issue with 1M interval).
                            self._candles.append(candle)

                        elif candle[0] == int(self._candles[-1][0]):
                            self._candles.pop()
                            self._candles.append(candle)
