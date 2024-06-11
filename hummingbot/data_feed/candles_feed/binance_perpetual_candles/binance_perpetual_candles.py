import asyncio
import logging
from typing import Any, Dict, Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
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

    async def fetch_candles(self,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit: Optional[int] = 500):
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"symbol": self._ex_trading_pair, "interval": self.interval, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)

        return np.array(candles)[:, [0, 1, 2, 3, 4, 5, 7, 8, 9, 10]].astype(float)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            candle_params = []
            candle_params.append(f"{self._ex_trading_pair.lower()}@kline_{self.interval}")
            payload = {
                "method": "SUBSCRIBE",
                "params": candle_params,
                "id": 1
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
            if data is not None and data.get("e") == "kline":  # data will be None when the websocket is disconnected
                timestamp = data["k"]["t"]
                open = data["k"]["o"]
                low = data["k"]["l"]
                high = data["k"]["h"]
                close = data["k"]["c"]
                volume = data["k"]["v"]
                quote_asset_volume = data["k"]["q"]
                n_trades = data["k"]["n"]
                taker_buy_base_volume = data["k"]["V"]
                taker_buy_quote_volume = data["k"]["Q"]
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
