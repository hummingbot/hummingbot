import asyncio
import os
from collections import deque
from typing import List, Optional

import numpy as np
import pandas as pd
from bidict import bidict

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig


class CandlesBase(NetworkBase):
    """
    This class serves as a base class for fetching and storing candle data from a cryptocurrency exchange.
    The class uses the Rest and WS Assistants for all the IO operations, and a double-ended queue to store candles.
    Also implements the Throttler module for API rate limiting, but it's not so necessary since the realtime data should
    be updated via websockets mainly.
    """
    interval_to_seconds = bidict({
        "1s": 1,
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600,
        "8h": 28800,
        "12h": 43200,
        "1d": 86400,
        "3d": 259200,
        "1w": 604800,
        "1M": 2592000
    })
    columns = ["timestamp", "open", "high", "low", "close", "volume", "quote_asset_volume",
               "n_trades", "taker_buy_base_volume", "taker_buy_quote_volume"]

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__()
        async_throttler = AsyncThrottler(rate_limits=self.rate_limits)
        self._api_factory = WebAssistantsFactory(throttler=async_throttler)
        self.max_records = max_records
        self._candles = deque(maxlen=max_records)
        self._listen_candles_task: Optional[asyncio.Task] = None
        self._trading_pair = trading_pair
        self._ex_trading_pair = self.get_exchange_trading_pair(trading_pair)
        self._ws_candle_available = asyncio.Event()
        self._ping_timeout = None
        if interval in self.intervals.keys():
            self.interval = interval
        else:
            self.logger().exception(
                f"Interval {interval} is not supported. Available Intervals: {self.intervals.keys()}")
            raise

    async def start_network(self):
        """
        This method starts the network and starts a task for listen_for_subscriptions.
        """
        await self.stop_network()
        await self.initialize_exchange_data()
        self._listen_candles_task = safe_ensure_future(self.listen_for_subscriptions())

    async def stop_network(self):
        """
        This method stops the network by canceling the _listen_candles_task task.
        """
        if self._listen_candles_task is not None:
            self._listen_candles_task.cancel()
            self._listen_candles_task = None

    async def initialize_exchange_data(self):
        """
        This method is used to set up the exchange data before starting the network.

        (I.E. get the trading pair quanto multiplier, special trading pair or symbol notation, etc.)
        """
        pass

    @property
    def ready(self):
        """
        This property returns a boolean indicating whether the _candles deque has reached its maximum length.
        """
        return len(self._candles) == self._candles.maxlen

    @property
    def name(self):
        raise NotImplementedError

    @property
    def rest_url(self):
        raise NotImplementedError

    @property
    def health_check_url(self):
        raise NotImplementedError

    @property
    def candles_url(self):
        raise NotImplementedError

    @property
    def candles_endpoint(self):
        raise NotImplementedError

    @property
    def candles_max_result_per_rest_request(self):
        raise NotImplementedError

    @property
    def wss_url(self):
        raise NotImplementedError

    @property
    def rate_limits(self):
        raise NotImplementedError

    @property
    def intervals(self):
        raise NotImplementedError

    async def check_network(self) -> NetworkStatus:
        raise NotImplementedError

    @property
    def interval_in_seconds(self):
        return self.get_seconds_from_interval(self.interval)

    @property
    def candles_df(self) -> pd.DataFrame:
        """
        This property returns the candles stored in the _candles deque as a Pandas DataFrame.
        """
        return pd.DataFrame(self._candles, columns=self.columns, dtype=float)

    def get_exchange_trading_pair(self, trading_pair):
        raise NotImplementedError

    def load_candles_from_csv(self, data_path: str):
        """
        This method loads the candles from a CSV file.
        :param data_path: data path that holds the CSV file
        """
        filename = f"candles_{self.name}_{self.interval}.csv"
        file_path = os.path.join(data_path, filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{file_path}' does not exist.")
        df = pd.read_csv(file_path)
        df.sort_values(by="timestamp", ascending=False, inplace=True)
        self._candles.extendleft(df.values.tolist())

    async def get_historical_candles(self, config: HistoricalCandlesConfig):
        try:
            await self.initialize_exchange_data()
            all_candles = []
            current_end_time = config.end_time + self.interval_in_seconds
            current_start_time = config.start_time - self.interval_in_seconds
            while current_end_time >= current_start_time:
                missing_records = int((current_end_time - current_start_time) / self.interval_in_seconds)
                fetched_candles = await self.fetch_candles(end_time=current_end_time, limit=missing_records)
                if fetched_candles.size <= 1:
                    break
                all_candles.append(fetched_candles)
                last_timestamp = self.ensure_timestamp_in_seconds(
                    fetched_candles[0][0])  # Assuming the first column is the timestamp
                current_end_time = last_timestamp - self.interval_in_seconds
                self.check_candles_sorted_and_equidistant(all_candles)
            final_candles = np.concatenate(all_candles[::-1], axis=0) if all_candles else np.array([])
            candles_df = pd.DataFrame(final_candles, columns=self.columns)
            candles_df.drop_duplicates(subset=["timestamp"], inplace=True)
            candles_df = candles_df[
                (candles_df["timestamp"] <= config.end_time) & (candles_df["timestamp"] >= config.start_time)]
            return candles_df
        except Exception as e:
            self.logger().exception(f"Error fetching historical candles: {str(e)}")

    def check_candles_sorted_and_equidistant(self, candles: np.ndarray):
        """
        This method checks if the given candles are sorted by timestamp in ascending order and equidistant.
        :param candles: numpy array with the candles
        """
        timestamps = [candle[0] for candle in candles]
        if len(self._candles) <= 1:
            return
        if not np.all(np.diff(timestamps) >= 0):
            self.logger().warning("Candles are not sorted by timestamp in ascending order.")
            self._reset_candles()
            return
        timestamp_steps = np.unique(np.diff(timestamps))
        interval_in_seconds = self.get_seconds_from_interval(self.interval)
        if not np.all(timestamp_steps == interval_in_seconds):
            self.logger().warning("Candles are malformed. Restarting...")
            self._reset_candles()
            return

    def _reset_candles(self):
        self._ws_candle_available.clear()
        self._candles.clear()

    async def fetch_candles(self,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit: Optional[int] = None):
        if start_time is None and end_time is None:
            raise ValueError("Either the start time or end time must be specified.")
        if limit is None:
            limit = self.candles_max_result_per_rest_request - 1

        candles_to_fetch = min(self.candles_max_result_per_rest_request - 1, limit)
        if end_time is None:
            end_time = start_time + self.interval_in_seconds * candles_to_fetch
        if start_time is None:
            start_time = end_time - self.interval_in_seconds * candles_to_fetch

        params = self._get_rest_candles_params(start_time, end_time)
        headers = self._get_rest_candles_headers()
        rest_assistant = await self._api_factory.get_rest_assistant()
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=self.candles_endpoint,
                                                       params=params,
                                                       headers=headers)
        arr = self._parse_rest_candles(candles, end_time)
        return np.array(arr).astype(float)

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = None) -> dict:
        """
        This method returns the parameters for the candles REST request.

        :param start_time: the start time of the candles data to fetch
        :param end_time: the end time of the candles data to fetch
        """
        raise NotImplementedError

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        """
        This method parses the candles data fetched from the REST API.

        - Timestamp must be in seconds
        - The array must be sorted by timestamp in ascending order. Oldest first, newest last.
        - The array must be in the format: [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades,
        taker_buy_base_volume, taker_buy_quote_volume]

        :param data: the candles data fetched from the REST API
        """
        raise NotImplementedError

    def _get_rest_candles_headers(self):
        """
        This method returns the headers for the candles REST request.
        """
        pass

    async def fill_historical_candles(self):
        """
        This method fills the historical candles in the _candles deque until it reaches the maximum length.
        """
        while not self.ready:
            await self._ws_candle_available.wait()
            try:
                end_timestamp = int(self._candles[0][0])
                missing_records = self._candles.maxlen - len(self._candles)
                candles: np.ndarray = await self.fetch_candles(end_time=end_timestamp, limit=missing_records)
                records_to_add = min(missing_records, len(candles))
                self._candles.extendleft(candles[-records_to_add:][::-1])
            except asyncio.CancelledError:
                raise
            except ValueError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when getting historical klines. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)
        self.check_candles_sorted_and_equidistant(self._candles)

    async def listen_for_subscriptions(self):
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
                    "Unexpected error occurred when listening to public klines. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)
            finally:
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=self.wss_url, ping_timeout=self._ping_timeout)
        return ws

    @property
    def _ping_payload(self):
        return None

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            subscribe_candles_request: WSJSONRequest = WSJSONRequest(payload=self.ws_subscription_payload())
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

    def ws_subscription_payload(self):
        """
        This method returns the subscription payload for the websocket connection.
        """
        raise NotImplementedError

    async def _process_websocket_messages_task(self, websocket_assistant: WSAssistant):
        # TODO: Isolate ping pong logic
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            parsed_message = self._parse_websocket_message(data)
            # parsed messages may be ping or pong messages
            if isinstance(parsed_message, WSJSONRequest):
                await websocket_assistant.send(request=parsed_message)
            elif isinstance(parsed_message, dict):
                candles_row = np.array([parsed_message["timestamp"],
                                        parsed_message["open"],
                                        parsed_message["high"],
                                        parsed_message["low"],
                                        parsed_message["close"],
                                        parsed_message["volume"],
                                        parsed_message["quote_asset_volume"],
                                        parsed_message["n_trades"],
                                        parsed_message["taker_buy_base_volume"],
                                        parsed_message["taker_buy_quote_volume"]]).astype(float)
                if len(self._candles) == 0:
                    self._candles.append(candles_row)
                    self._ws_candle_available.set()
                    safe_ensure_future(self.fill_historical_candles())
                else:
                    latest_timestamp = int(self._candles[-1][0])
                    current_timestamp = int(parsed_message["timestamp"])
                    if current_timestamp > latest_timestamp:
                        self._candles.append(candles_row)
                    elif current_timestamp == latest_timestamp:
                        self._candles[-1] = candles_row

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        while True:
            try:
                await asyncio.wait_for(self._process_websocket_messages_task(websocket_assistant=websocket_assistant),
                                       timeout=self._ping_timeout)
            except asyncio.TimeoutError:
                if self._ping_timeout is not None:
                    ping_request = WSJSONRequest(payload=self._ping_payload)
                    await websocket_assistant.send(request=ping_request)

    def _parse_websocket_message(self, data: dict):
        """
        This method must be implemented by a subclass to parse the websocket message into a dictionary with the
        candlestick data.

        The extracted data is stored in a dict with the following keys:
            - timestamp: The timestamp of the candlestick in seconds.
            - open: The opening price of the candlestick.
            - high: The highest price of the candlestick.
            - low: The lowest price of the candlestick.
            - close: The closing price of the candlestick.
            - volume: The volume of the candlestick.
            - quote_asset_volume: The quote asset volume of the candlestick.
            - n_trades: The number of trades of the candlestick.
            - taker_buy_base_volume: The taker buy base volume of the candlestick.
            - taker_buy_quote_volume: The taker buy quote volume of the candlestick.

        :param data: the websocket message data
        :return: dictionary with the candlestick data
        """
        raise NotImplementedError

    @staticmethod
    async def _sleep(delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        websocket_assistant and await websocket_assistant.disconnect()
        self._candles.clear()

    def get_seconds_from_interval(self, interval: str) -> int:
        """
        This method returns the number of seconds from the interval string.
        :param interval: interval string
        :return: number of seconds
        """
        return self.interval_to_seconds[interval]

    @staticmethod
    def ensure_timestamp_in_seconds(timestamp: float) -> float:
        """
        Ensure the given timestamp is in seconds.

        Args:
        - timestamp (int): The input timestamp which could be in seconds, milliseconds, or microseconds.

        Returns:
        - int: The timestamp in seconds.

        Raises:
        - ValueError: If the timestamp is not in a recognized format.
        """
        timestamp_int = int(float(timestamp))
        if timestamp_int >= 1e18:  # Nanoseconds
            return timestamp_int / 1e9
        elif timestamp_int >= 1e15:  # Microseconds
            return timestamp_int / 1e6
        elif timestamp_int >= 1e12:  # Milliseconds
            return timestamp_int / 1e3
        elif timestamp_int >= 1e9:  # Seconds
            return timestamp_int
        else:
            raise ValueError(
                "Timestamp is not in a recognized format. Must be in seconds, milliseconds, microseconds or nanoseconds.")
