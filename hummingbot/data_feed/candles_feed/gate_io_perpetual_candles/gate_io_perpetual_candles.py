import asyncio
import logging
import time
from typing import Any, Dict, Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.gate_io_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class GateioPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)
        self.quanto_multiplier = None

    @property
    def name(self):
        return f"gate_io_perpetual_{self._trading_pair}"

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

    async def start_network(self):
        """
        This method starts the network and starts a task for listen_for_subscriptions.
        """
        await self.stop_network()
        await self.get_exchange_trading_pair_quanto_multiplier()
        self._listen_candles_task = safe_ensure_future(self.listen_for_subscriptions())

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "_")

    async def get_exchange_trading_pair_quanto_multiplier(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=self.rest_url + CONSTANTS.CONTRACT_INFO_URL.format(contract=self._ex_trading_pair),
            throttler_limit_id=CONSTANTS.CONTRACT_INFO_URL
        )
        quanto_multiplier = float(data.get("quanto_multiplier"))
        self.quanto_multiplier = quanto_multiplier
        return quanto_multiplier

    async def fetch_candles(self, start_time: Optional[int] = None, end_time: Optional[int] = None,
                            limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST):
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"contract": self._ex_trading_pair, "interval": self.interval, "limit": limit}

        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)
        new_hb_candles = []
        for i in candles:
            timestamp_ms = i.get("t") * 1e3
            open = i.get("o")
            high = i.get("h")
            low = i.get("l")
            close = i.get("c")
            volume = i.get("v") * self.quanto_multiplier
            quote_asset_volume = i.get("sum")
            # no data field
            n_trades = 0
            taker_buy_base_volume = 0
            taker_buy_quote_volume = 0
            new_hb_candles.append([timestamp_ms, open, high, low, close, volume,
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
                "time": int(time.time()),
                "channel": CONSTANTS.WS_CANDLES_ENDPOINT,
                "event": "subscribe",
                "payload": [self.interval, self._ex_trading_pair]
            }
            subscribe_candles_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_candles_request)
            if self.interval == '1m':
                self.logger().warning("The 1m K-line on gateioperpetual is currently not accurate due to discrepancies between the official ws and rs data...")
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

            if data.get("event") == "update" and data.get("channel") == "futures.candlesticks":
                for i in data["result"]:
                    timestamp_ms = int(i["t"] * 1e3)
                    open = i["o"]
                    high = i["h"]
                    low = i["l"]
                    close = i["c"]
                    volume = i["v"] * self.quanto_multiplier
                    # no data field
                    quote_asset_volume = 0
                    n_trades = 0
                    taker_buy_base_volume = 0
                    taker_buy_quote_volume = 0
                    if len(self._candles) == 0:
                        self._candles.append(np.array([timestamp_ms, open, high, low, close, volume,
                                                       quote_asset_volume, n_trades, taker_buy_base_volume,
                                                       taker_buy_quote_volume]))
                        safe_ensure_future(self.fill_historical_candles())
                    elif timestamp_ms > int(self._candles[-1][0]):
                        # TODO: validate also that the diff of timestamp == interval (issue with 1w, 30d interval).
                        self._candles.append(np.array([timestamp_ms, open, high, low, close, volume,
                                                       quote_asset_volume, n_trades, taker_buy_base_volume,
                                                       taker_buy_quote_volume]))
                    elif timestamp_ms == int(self._candles[-1][0]):
                        self._candles.pop()
                        self._candles.append(np.array([timestamp_ms, open, high, low, close, volume,
                                                       quote_asset_volume, n_trades, taker_buy_base_volume,
                                                       taker_buy_quote_volume]))
