import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils as web_utils
from hummingbot.client.config.security import Security
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_auth import CoinbaseAdvancedTradeAuth
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants import (
    DEFAULT_DOMAIN,
    REST_URL,
    SERVER_TIME_EP,
    WSS_URL,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class CoinbaseAdvancedTradeSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None
    _ws_subscriptions: Dict[str, Any] = {}

    web_utils = web_utils

    class NotEnoughDataAvailableError(Exception):
        pass

    class HistoricalCallOnEmptyCandles(Exception):
        pass

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)
        self._public_api_factory = self._api_factory
        self._api_factory = None
        self.logger().debug(f"Initializing {self.name} candles feed...")

    async def _build_auth_api_factory(self) -> WebAssistantsFactory:
        """Builds the API factory with authentication."""
        time_sync = TimeSynchronizer()
        await Security.wait_til_decryption_done()
        api_keys = Security.api_keys("coinbase_advanced_trade")
        return web_utils.build_api_factory(
            throttler=AsyncThrottler(rate_limits=self.rate_limits),
            time_synchronizer=time_sync,
            domain=DEFAULT_DOMAIN,
            auth=CoinbaseAdvancedTradeAuth(
                api_key=api_keys["coinbase_advanced_trade_api_key"],
                secret_key=api_keys["coinbase_advanced_trade_api_secret"],
                time_provider=time_sync))

    @property
    def name(self) -> str:
        """Name of the exchange with candle pair tracked."""
        return f"coinbase_advanced_trade_{self._trading_pair}"

    @property
    def rest_url(self) -> str:
        """REST URL for the exchange."""
        return REST_URL.format(domain=DEFAULT_DOMAIN)

    @property
    def wss_url(self) -> str:
        """Websocket URL for the exchange."""
        return WSS_URL.format(domain=DEFAULT_DOMAIN)

    @property
    def candles_url(self) -> str:
        """Candles URL for the exchange."""
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT.format(product_id=self._ex_trading_pair)

    @property
    def health_check_url(self) -> str:
        """Candles URL for the exchange."""
        # This is correct: the SERVER_TIME_EP is not authenticated, but use the 'private' v3 URL
        # Changelog of Coinbase on Feb22nd 24
        return web_utils.private_rest_url(path_url=SERVER_TIME_EP)

    @property
    def rate_limits(self) -> List[RateLimit]:
        """Rate limits for the exchange."""
        return CONSTANTS.RATE_LIMITS

    @property
    def intervals(self) -> Dict[str, int]:
        """Intervals supported by the exchange."""
        return CONSTANTS.INTERVALS

    @property
    def candle_keys_order(self) -> Tuple[str, ...]:
        """Order in which to arrange the REST and WSS candle information keys"""
        return "start", "open", "high", "low", "close", "volume"

    @property
    def candles_df(self) -> pd.DataFrame:
        """Dataframe with the candles' information."""
        df = pd.DataFrame(self._candles, columns=["timestamp"] + list(self.candle_keys_order[1:]), dtype=float)
        df = df.reindex(columns=self.columns, fill_value=0.0)
        df["timestamp"] = df["timestamp"] * 1000
        return df.sort_values(by="timestamp", ascending=True)

    async def check_network(self) -> NetworkStatus:
        """Verifies the exchange status."""
        if self._api_factory is None or self._api_factory is self._public_api_factory:
            self._api_factory = await self._build_auth_api_factory()

        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=web_utils.private_rest_url(path_url=SERVER_TIME_EP),
            throttler_limit_id=SERVER_TIME_EP,
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair) -> str:
        """Returns the trading pair in the format required by the exchange."""
        return trading_pair.replace("-", "-")

    def _get_valid_start_time(self, end_time: int, start_time: int | None = None) -> int:
        """Returns the start time of the candles deque."""
        interval_s: float = self.get_seconds_from_interval(self.interval)
        _start_time: int = end_time - int(min(self._candles.maxlen, CONSTANTS.MAX_CANDLES_SIZE) * interval_s)
        start_time: int = max(start_time or _start_time, _start_time)
        return start_time

    async def fetch_candles(
            self,
            end_time: int | None = None,
            start_time: int | None = None,
            limit: int | None = 500) -> np.ndarray:
        """
        Fetches candles from the exchange.
        :param start_time: the start time of the candles to be fetched
        :param end_time: the end time of the candles to be fetched
        :param limit: the quantity of candles to be fetched
        :return: a numpy array with the candles
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getcandles
        """
        if self._api_factory is None or self._api_factory is self._public_api_factory:
            self._api_factory = await self._build_auth_api_factory()

        rest_assistant = await self._api_factory.get_rest_assistant()

        end_time = end_time or await web_utils.get_current_server_time_s()
        start_time = self._get_valid_start_time(end_time=end_time, start_time=start_time)

        params = {"granularity": CONSTANTS.INTERVALS[self.interval],
                  "start": str(start_time),
                  "end": str(end_time)}

        data: Dict[str, Any] = await rest_assistant.execute_request(
            url=self.candles_url,
            throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT_ID,
            params=params,
            is_auth_required=True,
        )

        self.logger().debug(f"fetch_candles() returned {len(data['candles'])} candles")
        return np.array(
            [
                [float(candle[key]) for key in self.candle_keys_order]
                for candle in data["candles"]
            ]
        )

    async def fill_historical_candles(self, end_time: int | None = None) -> None:
        """
        Fills the historical candles deque with the candles fetched from the exchange.
        Ideally, one request should provide the number of candles needed to fill the deque.
        """
        while not self.is_ready:
            end_timestamp: int = end_time or int(self._candles[0][0])
            try:
                candles = await self.fetch_candles(end_time=end_timestamp)

                if len(candles) == 0:
                    # No candles were fetched (Coinbase Advanced Trade may only have 9 days of candles)
                    raise CoinbaseAdvancedTradeSpotCandles.NotEnoughDataAvailableError
            except asyncio.CancelledError:
                raise
            except (CoinbaseAdvancedTradeSpotCandles.NotEnoughDataAvailableError,
                    StopAsyncIteration):
                self.logger().error("There is not enough data available to fill historical"
                                    f" candles for {self.name}. Relying upon websocket feed")
                break
            except Exception as e:
                self.logger().exception(
                    f"Unexpected error occurred when getting historical candles {e}.\n"
                    f"   end_timestamp: {end_timestamp}\n"
                    f"Retrying in 1 seconds...",
                )
                await self._sleep(1.0)
                continue

            # Sort in reversed order to fill the deque from the oldest to the newest candle
            sorted_indices = candles[:, 0].argsort()[::-1]
            candles = candles[sorted_indices]

            # Verify that we don't override the last candle fetched with websocket (initial value)
            if candles[0][0] == end_timestamp:
                candles = candles[1:]

            # we are computing again the quantity of records again since the websocket process is able to
            # modify the deque and if we extend it, the new observations are going to be dropped.
            missing_records = self._candles.maxlen - len(self._candles)
            if missing_records > len(candles):
                # Not enough candles were fetched to fill the deque, possibly the end time did not match well
                self.logger().debug(f"Missing {missing_records - len(candles)} candles to fill the deque. Attempting "
                                    "to fetch more.")
                self._candles.extendleft(candles)
            else:
                self._candles.extendleft(candles[:missing_records])

    async def listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        if self.interval in CONSTANTS.WS_INTERVALS:
            self.logger().debug(f"Using websocket for {self.interval} (in {CONSTANTS.WS_INTERVALS})")
            await self._listen_for_subscriptions()
        else:
            self.logger().warning(f"Using REST loop for {self.interval} (not in {CONSTANTS.WS_INTERVALS})")
            await self._listen_to_fetch()

    async def _listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(websocket_assistant=ws)

            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public klines. Retrying in 1 "
                    "seconds...",
                )
                await self._sleep(1.0)
            finally:
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _listen_to_fetch(self):
        """
        Repeatedly calls fetch_candles on interval.
        """
        while True:
            try:
                end_time = await web_utils.get_current_server_time_s()
                await self.fill_historical_candles(end_time=int(end_time))
                await self._sleep(self.get_seconds_from_interval(self.interval))

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public REST candle call. Retrying in 1 "
                    "seconds...",
                )
                await self._sleep(1.0)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        if self._api_factory is None:
            self._api_factory = await self._build_auth_api_factory()

        return await super()._connected_websocket_assistant()

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        if self._ws_subscriptions.get(self._trading_pair) is not None:
            return

        try:
            for channel in ("candles",):
                payload = {
                    "type": "subscribe",
                    "product_ids": [self._ex_trading_pair],
                    "channel": channel,
                }
                self.logger().debug(f"Subscribing to public {channel} with payload: {payload}")

                await ws.send(WSJSONRequest(payload=payload, is_auth_required=True))
                self._ws_subscriptions[self._trading_pair] = True
                self.logger().info(f"Subscribed to public {channel}...")
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
            self.logger().debug(f"Received message from websocket: {data}")

            if data is not None and data.get("type") == "error":
                self._ws_subscriptions.pop(self._trading_pair)
                self.logger().error(f"Failed to subscribed to public candles: {data.get('message')}")

            if data is not None and data.get("channel") == "candles":
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
