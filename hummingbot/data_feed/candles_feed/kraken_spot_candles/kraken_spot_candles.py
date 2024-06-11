import asyncio
import logging
from copy import deepcopy
from typing import List, Optional

import numpy as np
import pandas as pd

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.kraken_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class KrakenSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 720):
        if max_records > 720:
            raise Exception("Kraken only supports a maximum of 720 records.")
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"kraken_{self._trading_pair}"

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

    @property
    def candles_df(self) -> pd.DataFrame:
        df = pd.DataFrame(self._candles, columns=self.columns, dtype=float)
        df["timestamp"] = df["timestamp"] * 1000
        return df.sort_values(by="timestamp", ascending=True)

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def convert_to_exchange_symbol(self, symbol: str) -> str:
        inverted_kraken_to_hb_map = {v: k for k, v in CONSTANTS.KRAKEN_TO_HB_MAP.items()}
        return inverted_kraken_to_hb_map.get(symbol, symbol)

    def get_exchange_trading_pair(self, hb_trading_pair: str, delimiter: str = "") -> str:
        """
        Note: The result of this method can safely be used to submit/make queries.
        Result shouldn't be used to parse responses as Kraken add special formating to most pairs.
        """
        if "-" in hb_trading_pair:
            base, quote = hb_trading_pair.split("-")
        elif "/" in hb_trading_pair:
            base, quote = hb_trading_pair.split("/")
        else:
            return hb_trading_pair
        base = self.convert_to_exchange_symbol(base)
        quote = self.convert_to_exchange_symbol(quote)

        exchange_trading_pair = f"{base}{delimiter}{quote}"
        return exchange_trading_pair

    async def fetch_candles(self,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit: Optional[int] = 720):
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"pair": self._ex_trading_pair, "interval": CONSTANTS.INTERVALS[self.interval], "since": start_time}
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)

        data: List = next(iter(candles["result"].values()))

        new_hb_candles = []
        for i in data:
            timestamp = int(float(i[0]))
            open = i[1]
            high = i[2]
            low = i[3]
            close = i[4]
            volume = i[6]
            # vwap = i[5] Volume weighted average price within interval
            quote_asset_volume = float(volume) * float(i[5])
            # no data field
            n_trades = 0
            taker_buy_base_volume = 0
            taker_buy_quote_volume = 0
            new_hb_candles.append([timestamp, open, high, low, close, volume,
                                   quote_asset_volume, n_trades, taker_buy_base_volume,
                                   taker_buy_quote_volume])
        return np.array(new_hb_candles).astype(float)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            payload = {
                "event": "subscribe",
                "pair": [self.get_exchange_trading_pair(self._trading_pair, '/')],
                "subscription": {"name": CONSTANTS.WS_CANDLES_ENDPOINT,
                                 "interval": int(CONSTANTS.INTERVALS[self.interval])}
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
            data: List = ws_response.data
            if not (type(data) is dict and "event" in data.keys() and
                    data["event"] in ["heartbeat", "systemStatus", "subscriptionStatus"]):
                if data[-2][:4] == "ohlc":
                    timestamp = int(float(data[1][1])) - int(CONSTANTS.INTERVALS[self.interval]) * 60
                    open = data[1][2]
                    high = data[1][3]
                    low = data[1][4]
                    close = data[1][5]
                    volume = data[1][7]
                    # vwap = data[1][6] Volume weighted average price within interval
                    quote_asset_volume = float(volume) * float(data[1][6])
                    # no data field
                    n_trades = 0
                    taker_buy_base_volume = 0
                    taker_buy_quote_volume = 0
                    if len(self._candles) == 0:
                        self._candles.append(np.array([timestamp, open, high, low, close, volume,
                                                       quote_asset_volume, n_trades, taker_buy_base_volume,
                                                       taker_buy_quote_volume]))
                        await self.fill_historical_candles()
                    elif timestamp > int(self._candles[-1][0]):
                        # TODO: validate also that the diff of timestamp == interval (issue with 30d interval).
                        interval = int(CONSTANTS.INTERVALS[self.interval]) * 60
                        total_interval_time = timestamp - int(self._candles[-1][0])
                        the_number_of_interval = total_interval_time // interval
                        if the_number_of_interval >= 2:
                            for i in range(1, the_number_of_interval):
                                old_data = deepcopy(self._candles[-1])
                                new_timestamp = int(self._candles[-1][0]) + interval
                                old_data[0] = new_timestamp
                                self._candles.append(old_data)
                        self._candles.append(np.array([timestamp, open, high, low, close, volume,
                                                       quote_asset_volume, n_trades, taker_buy_base_volume,
                                                       taker_buy_quote_volume]))
                    elif timestamp == int(self._candles[-1][0]):
                        self._candles.pop()
                        self._candles.append(np.array([timestamp, open, high, low, close, volume,
                                                       quote_asset_volume, n_trades, taker_buy_base_volume,
                                                       taker_buy_quote_volume]))
