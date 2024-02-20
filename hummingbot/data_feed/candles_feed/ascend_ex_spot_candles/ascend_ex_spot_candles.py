import asyncio
import logging
from typing import Any, Dict, Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
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

    async def fetch_candles(self,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit: Optional[int] = 500):
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"symbol": self._ex_trading_pair, "interval": CONSTANTS.INTERVALS[self.interval], "n": limit}
        if start_time:
            params["from"] = start_time
        if end_time:
            params["to"] = end_time
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)
        new_hb_candles = []
        for i in candles["data"]:
            timestamp_ms = i["data"]["ts"]
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
            new_hb_candles.append([timestamp_ms, open, high, low, close, volume,
                                   quote_asset_volume, n_trades, taker_buy_base_volume,
                                   taker_buy_quote_volume])
        return np.array(new_hb_candles).astype(float)

    async def fill_historical_candles(self):
        max_request_needed = (self._candles.maxlen // 1000) + 1
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
                    "Unexpected error occurred when getting historical klines. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            payload = {"op": CONSTANTS.SUB_ENDPOINT_NAME,
                       "ch": f"bar:{CONSTANTS.INTERVALS[self.interval]}:{self._ex_trading_pair}"}
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
            if data.get("m") == "ping":
                pong_payloads = {"op": "pong"}
                pong_request = WSJSONRequest(payload=pong_payloads)
                await websocket_assistant.send(request=pong_request)
            if data is not None and data.get("m") == "bar":  # data will be None when the websocket is disconnected
                timestamp = data["data"]["ts"]
                open = data["data"]["o"]
                high = data["data"]["h"]
                low = data["data"]["l"]
                close = data["data"]["c"]
                quote_asset_volume = data["data"]["v"]
                volume = 0
                n_trades = 0
                taker_buy_base_volume = 0
                taker_buy_quote_volume = 0
                if len(self._candles) == 0:
                    self._candles.append(np.array([timestamp, open, high, low, close, volume,
                                                   quote_asset_volume, n_trades, taker_buy_base_volume,
                                                   taker_buy_quote_volume]))
                    safe_ensure_future(self.fill_historical_candles())
                elif timestamp > int(self._candles[-1][0]):
                    # TODO: validate also that the diff of timestamp == interval (issue with 1M interval).
                    self._candles.append(np.array([timestamp, open, high, low, close, volume,
                                                   quote_asset_volume, n_trades, taker_buy_base_volume,
                                                   taker_buy_quote_volume]))
                elif timestamp == int(self._candles[-1][0]):
                    self._candles.pop()
                    self._candles.append(np.array([timestamp, open, high, low, close, volume,
                                                   quote_asset_volume, n_trades, taker_buy_base_volume,
                                                   taker_buy_quote_volume]))
