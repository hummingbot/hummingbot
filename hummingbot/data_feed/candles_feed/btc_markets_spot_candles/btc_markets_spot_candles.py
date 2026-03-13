import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from dateutil.parser import parse as dateparse

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class BtcMarketsSpotCandles(CandlesBase):
    """
    BTC Markets implementation for fetching candlestick data.

    Note: BTC Markets doesn't support WebSocket for candles, so we use constant polling.
    This implementation maintains a constant polling rate to capture real-time updates
    and fills gaps with heartbeat candles to maintain equidistant intervals.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)

        self._consecutive_empty_responses = 0
        self._historical_fill_in_progress = False

        # Task management for polling
        self._polling_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._is_running = False

    @property
    def name(self):
        return f"btc_markets_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        # BTC Markets doesn't support WebSocket for candles
        return CONSTANTS.WSS_URL

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def candles_url(self):
        market_id = self.get_exchange_trading_pair(self._trading_pair)
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT.format(market_id=market_id)

    @property
    def candles_endpoint(self):
        return CONSTANTS.CANDLES_ENDPOINT

    @property
    def candles_max_result_per_rest_request(self):
        return CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST

    @property
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def intervals(self):
        return CONSTANTS.INTERVALS

    @property
    def _last_real_candle(self):
        """Get the last candle, filtering out heartbeats if needed."""
        if not self._candles:
            return None
        # Find last candle with volume > 0, or just return last candle
        for candle in reversed(self._candles):
            if candle[5] > 0:  # volume > 0
                return candle
        return self._candles[-1]

    @property
    def _current_candle_timestamp(self):
        return self._candles[-1][0] if self._candles else None

    async def start_network(self):
        """
        Start the network and begin polling.
        """
        await self.stop_network()
        await self.initialize_exchange_data()
        self._is_running = True
        self._shutdown_event.clear()
        self._polling_task = asyncio.create_task(self._polling_loop())

    async def stop_network(self):
        """
        Stop the network by gracefully shutting down the polling task.
        """
        if self._polling_task and not self._polling_task.done():
            self._is_running = False
            self._shutdown_event.set()

            try:
                # Wait for graceful shutdown
                await asyncio.wait_for(self._polling_task, timeout=10.0)
            except asyncio.TimeoutError:
                self.logger().warning("Polling task didn't stop gracefully, cancelling...")
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass

        self._polling_task = None
        self._is_running = False

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url, throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        """
        Converts from the Hummingbot trading pair format to the exchange's trading pair format.
        BTC Markets uses the same format so no conversion is needed.
        """
        return trading_pair

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return False

    def _get_rest_candles_params(
        self, start_time: Optional[int] = None, end_time: Optional[int] = None, limit: Optional[int] = None
    ) -> dict:
        """
        Generates parameters for the REST API request to fetch candles.
        """
        params = {
            "timeWindow": self.intervals[self.interval],
        }

        if start_time is None and end_time is None:
            # For real-time polling, fetch a small number of recent candles
            params["limit"] = limit if limit is not None else 3
        else:
            # Use timestamp parameters for historical data
            params["limit"] = min(limit if limit is not None else 1000, 1000)

            if start_time:
                start_iso = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")
                params["from"] = start_iso

            if end_time:
                end_iso = datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")
                params["to"] = end_iso

        return params

    def _parse_rest_candles(self, data: List[List[str]], end_time: Optional[int] = None) -> List[List[float]]:
        """
        Parse the REST API response into the standard candle format.
        """
        if not isinstance(data, list) or len(data) == 0:
            return []

        new_hb_candles = []
        for i, candle in enumerate(data):
            try:
                if not isinstance(candle, list) or len(candle) < 6:
                    self.logger().warning(f"Invalid candle format at index {i}: {candle}")
                    continue

                timestamp = self.ensure_timestamp_in_seconds(dateparse(candle[0]).timestamp())
                open_price = float(candle[1])
                high = float(candle[2])
                low = float(candle[3])
                close = float(candle[4])
                volume = float(candle[5])

                # BTC Markets doesn't provide these values
                quote_asset_volume = 0.0
                n_trades = 0.0
                taker_buy_base_volume = 0.0
                taker_buy_quote_volume = 0.0

                new_hb_candles.append(
                    [
                        timestamp,
                        open_price,
                        high,
                        low,
                        close,
                        volume,
                        quote_asset_volume,
                        n_trades,
                        taker_buy_base_volume,
                        taker_buy_quote_volume,
                    ]
                )

            except Exception as e:
                self.logger().error(f"Error parsing candle {candle}: {e}")

        # Sort by timestamp (oldest first)
        new_hb_candles.sort(key=lambda x: x[0])
        return new_hb_candles

    def _create_heartbeat_candle(self, timestamp: float) -> List[float]:
        """
        Create a "heartbeat" candle for periods with no trading activity.
        Uses the close price from the last real candle.
        """
        last_real = self._last_real_candle
        if last_real is not None:
            close_price = last_real[4]
        elif self._candles:
            close_price = self._candles[-1][4]
        else:
            close_price = 0.0

        return [timestamp, close_price, close_price, close_price, close_price, 0.0, 0.0, 0.0, 0.0, 0.0]

    def _fill_gaps_and_append(self, new_candle: List[float]):
        """
        Fill any gaps between last candle and new candle, then append the new candle.
        """
        if not self._candles:
            self._candles.append(new_candle)
            return

        last_timestamp = self._candles[-1][0]
        new_timestamp = new_candle[0]

        # Fill gaps with heartbeats
        current_timestamp = last_timestamp + self.interval_in_seconds
        while current_timestamp < new_timestamp:
            heartbeat = self._create_heartbeat_candle(current_timestamp)
            self._candles.append(heartbeat)
            self.logger().debug(f"Added heartbeat candle at {current_timestamp}")
            current_timestamp += self.interval_in_seconds

        # Append the new candle
        self._candles.append(new_candle)
        self.logger().debug(f"Added new candle at {new_timestamp}")

    def _ensure_heartbeats_to_current_time(self):
        """
        Ensure we have heartbeat candles up to the current time interval.
        Only creates heartbeats for complete intervals (not the current incomplete one).
        """
        if not self._candles:
            return

        current_time = self._time()
        current_interval_timestamp = self._round_timestamp_to_interval_multiple(current_time)
        last_candle_timestamp = self._candles[-1][0]

        # Only create heartbeats for complete intervals
        next_expected_timestamp = last_candle_timestamp + self.interval_in_seconds

        while next_expected_timestamp < current_interval_timestamp:
            heartbeat = self._create_heartbeat_candle(next_expected_timestamp)
            self._candles.append(heartbeat)
            self.logger().debug(f"Added heartbeat for time progression: {next_expected_timestamp}")
            next_expected_timestamp += self.interval_in_seconds

    async def fill_historical_candles(self):
        """
        Fill historical candles with heartbeats to maintain equidistant intervals.
        """
        if self._historical_fill_in_progress:
            return

        self._historical_fill_in_progress = True

        try:
            iteration = 0
            max_iterations = 20

            while not self.ready and len(self._candles) > 0 and iteration < max_iterations:
                iteration += 1

                try:
                    oldest_timestamp = self._candles[0][0]
                    missing_records = self._candles.maxlen - len(self._candles)

                    if missing_records <= 0:
                        break

                    end_timestamp = oldest_timestamp - self.interval_in_seconds
                    start_timestamp = end_timestamp - (missing_records * self.interval_in_seconds)

                    # Fetch real candles for this time range
                    real_candles = await self.fetch_candles(
                        start_time=start_timestamp, end_time=end_timestamp + self.interval_in_seconds
                    )

                    # Fill gaps with heartbeats
                    complete_candles = self._fill_historical_gaps_with_heartbeats(
                        real_candles, start_timestamp, end_timestamp
                    )

                    if complete_candles:
                        candles_to_add = (
                            complete_candles[-missing_records:]
                            if len(complete_candles) > missing_records
                            else complete_candles
                        )

                        # Add in reverse order to maintain chronological order
                        for candle in reversed(candles_to_add):
                            self._candles.appendleft(candle)
                    else:
                        break

                    await self._sleep(0.1)

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger().exception(f"Error during historical fill iteration {iteration}: {e}")
                    await self._sleep(1.0)

        finally:
            self._historical_fill_in_progress = False

    def _fill_historical_gaps_with_heartbeats(
        self, candles: List[List[float]], start_timestamp: float, end_timestamp: float
    ) -> List[List[float]]:
        """
        Fill gaps in historical candle data with heartbeat candles.
        """
        if not candles.any():
            # Generate all heartbeats
            result = []
            current_timestamp = self._round_timestamp_to_interval_multiple(start_timestamp)
            interval_count = 0

            while current_timestamp <= end_timestamp and interval_count < 1000:
                heartbeat = self._create_heartbeat_candle(current_timestamp)
                result.append(heartbeat)
                current_timestamp += self.interval_in_seconds
                interval_count += 1

            return result

        # Create map of real candles by timestamp
        candle_map = {self._round_timestamp_to_interval_multiple(c[0]): c for c in candles}

        # Fill complete time range
        result = []
        current_timestamp = self._round_timestamp_to_interval_multiple(start_timestamp)
        interval_count = 0

        while current_timestamp <= end_timestamp and interval_count < 1000:
            if current_timestamp in candle_map:
                result.append(candle_map[current_timestamp])
            else:
                heartbeat = self._create_heartbeat_candle(current_timestamp)
                result.append(heartbeat)

            current_timestamp += self.interval_in_seconds
            interval_count += 1

        return result

    async def fetch_recent_candles(self, limit: int = 3) -> List[List[float]]:
        """Fetch recent candles from the API."""
        try:
            params = {"timeWindow": self.intervals[self.interval], "limit": limit}

            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=self.candles_url,
                throttler_limit_id=self._rest_throttler_limit_id,
                params=params,
                method=self._rest_method,
            )

            return self._parse_rest_candles(response)

        except Exception as e:
            self.logger().error(f"Error fetching recent candles: {e}")
            return []

    async def _polling_loop(self):
        """
        Main polling loop - separated from listen_for_subscriptions for better testability.
        This method can be cancelled cleanly and tested independently.
        """
        try:
            self.logger().info(f"Starting constant polling for {self._trading_pair} candles")

            # Initial setup
            await self._initialize_candles()

            while self._is_running and not self._shutdown_event.is_set():
                try:
                    # Poll for updates
                    await self._poll_and_update_candles()

                    # Ensure heartbeats up to current time
                    self._ensure_heartbeats_to_current_time()

                    # Wait for either shutdown signal or polling interval
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=CONSTANTS.POLL_INTERVAL
                        )
                        # If we reach here, shutdown was requested
                        break
                    except asyncio.TimeoutError:
                        # Normal case - polling interval elapsed
                        continue

                except asyncio.CancelledError:
                    self.logger().info("Polling loop cancelled")
                    raise
                except Exception as e:
                    self.logger().exception(f"Unexpected error during polling: {e}")

                    # Wait before retrying, but also listen for shutdown
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=5.0
                        )
                        break
                    except asyncio.TimeoutError:
                        continue

        finally:
            self.logger().info("Polling loop stopped")
            self._is_running = False

    async def listen_for_subscriptions(self):
        """
        Legacy method for compatibility with base class.
        Now just delegates to the task-based approach.
        """
        if not self._is_running:
            await self.start_network()

        # Wait for the polling task to complete
        if self._polling_task:
            try:
                await self._polling_task
            except asyncio.CancelledError:
                self.logger().info("Listen for subscriptions cancelled")
                raise

    async def _poll_and_update_candles(self):
        """
        Fetch recent candles and update data structure.
        This method is now easily testable in isolation.
        """
        try:
            # Always fetch recent candles to get current candle updates
            recent_candles = await self.fetch_recent_candles(limit=3)

            if not recent_candles:
                self._consecutive_empty_responses += 1
                return

            # Reset empty response counter
            self._consecutive_empty_responses = 0
            latest_candle = recent_candles[-1]

            if not self._candles:
                # First initialization
                self._candles.append(latest_candle)
                self._ws_candle_available.set()
                safe_ensure_future(self.fill_historical_candles())
                return

            # Simple logic: append if newer, update if same timestamp
            last_timestamp = self._candles[-1][0]
            latest_timestamp = latest_candle[0]

            if latest_timestamp > last_timestamp:
                # New candle - fill gaps and append
                self._fill_gaps_and_append(latest_candle)
            elif latest_timestamp == last_timestamp:
                # Update current candle
                old_candle = self._candles[-1]
                self._candles[-1] = latest_candle

                # Log significant changes
                if abs(old_candle[4] - latest_candle[4]) > 0.0001 or abs(old_candle[5] - latest_candle[5]) > 0.0001:
                    self.logger().debug(
                        f"Updated current candle: close {old_candle[4]:.4f} -> {latest_candle[4]:.4f}, "
                        f"volume {old_candle[5]:.4f} -> {latest_candle[5]:.4f}"
                    )

        except Exception as e:
            self.logger().error(f"Error during polling: {e}")
            self._consecutive_empty_responses += 1

    async def _initialize_candles(self):
        """Initialize with recent candle data and start constant polling."""
        try:
            self.logger().info("Initializing candles with recent data...")

            candles = await self.fetch_recent_candles(limit=2)

            if candles:
                latest_candle = candles[-1]
                self._candles.append(latest_candle)
                self._ws_candle_available.set()
                safe_ensure_future(self.fill_historical_candles())
                self.logger().info(f"Initialized with candle at {latest_candle[0]}")
            else:
                self.logger().warning("No recent candles found during initialization")

        except Exception as e:
            self.logger().error(f"Failed to initialize candles: {e}")

    def ws_subscription_payload(self):
        """Not used for BTC Markets since WebSocket is not supported for candles."""
        raise NotImplementedError("WebSocket not supported for BTC Markets candles")

    def _parse_websocket_message(self, data):
        """Not used for BTC Markets since WebSocket is not supported for candles."""
        raise NotImplementedError("WebSocket not supported for BTC Markets candles")
