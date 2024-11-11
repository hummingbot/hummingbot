import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils as web_utils
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants import (
    DEFAULT_DOMAIN,
    REST_URL,
    SERVER_TIME_EP,
    WSS_URL,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_exchange import (
    CoinbaseExchangeThrottler,
)
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
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

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)
        self._api_factory = WebAssistantsFactory(throttler=CoinbaseExchangeThrottler)

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
        return []

    @property
    def intervals(self) -> Dict[str, int]:
        """Intervals supported by the exchange."""
        return CONSTANTS.INTERVALS

    @property
    def candles_endpoint(self):
        self.logger().debug(f"Getting candles endpoint for {self._ex_trading_pair}")
        raise CONSTANTS.CANDLES_ENDPOINT.format(product_id=self._ex_trading_pair)

    @property
    def _rest_throttler_limit_id(self):
        self.logger().debug(f"Getting rest throttler limit id for {CONSTANTS.CANDLES_ENDPOINT_ID}")
        return CONSTANTS.CANDLES_ENDPOINT_ID

    @property
    def candles_max_result_per_rest_request(self):
        return CONSTANTS.MAX_CANDLES_SIZE

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    async def start_network(self):
        """
        This method starts the network and starts a task for listen_for_subscriptions.
        """
        self.logger().debug("Starting network...")
        await self.stop_network()
        await self.initialize_exchange_data()
        self._listen_candles_task = safe_ensure_future(self.listen_for_subscriptions())
        self.logger().debug(f"Network started. {self._listen_candles_task}")

    async def check_network(self) -> NetworkStatus:
        """Verifies the exchange status."""
        self.logger().debug("Checking network...")
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            result = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=SERVER_TIME_EP),
                throttler_limit_id=SERVER_TIME_EP,
            )
            if result is not None:
                return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred when checking network status...")

        return NetworkStatus.NOT_CONNECTED

    def get_exchange_trading_pair(self, trading_pair) -> str:
        """Returns the trading pair in the format required by the exchange."""
        return trading_pair.replace("-", "-")

    @staticmethod
    def sanitize_data_to_interval(
            candles: np.ndarray,
            interval_in_s: int,
            sort: bool = True,
            from_start: bool = True,
            logger: HummingbotLogger | None = None
    ) -> np.ndarray:
        """Sanitizes the data to the interval."""
        def log(msg: str):
            if logger:
                logger.debug(f"{msg}")

        if len(candles) == 0:
            return candles

        new_candles: np.ndarray = candles
        if sort:
            log("   [Sanitize] Sorting")
            new_candles: np.ndarray = np.array(sorted(new_candles, key=lambda x: x[0], reverse=False))

        timestamps = [int(candle[0]) for candle in new_candles]
        timestamp_steps = np.unique(np.diff(timestamps))
        log(f"   [Sanitize] Timestamp steps: {timestamp_steps}")

        if not np.all(timestamp_steps == interval_in_s):
            if from_start:
                invalid_index = np.where(np.diff(timestamps) != interval_in_s)[0][0]
                new_candles = new_candles[:invalid_index]
            else:
                invalid_index = np.where(np.diff(timestamps[::-1]) != -interval_in_s)[0][0]
                new_candles = new_candles[-invalid_index:]
        log(f"   [Sanitize] Discarded: {len(candles) - len(new_candles)} candles")

        timestamps = [int(candle[0]) for candle in new_candles]
        timestamp_steps = np.unique(np.diff(timestamps))
        log(f"   [Sanitize] Timestamp steps: {timestamp_steps}")

        assert np.all(timestamp_steps == interval_in_s)
        return new_candles

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_CANDLES_SIZE) -> dict:
        params = {
            "granularity": CONSTANTS.INTERVALS[self.interval],
            "start": self.ensure_timestamp_in_seconds(start_time) if start_time else None,
        }
        if end_time:
            params["end"] = self.ensure_timestamp_in_seconds(end_time)
        self.logger().debug(f"REST candles params: {params}")
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        self.logger().debug(f"Received candles from {data['candles'][0]['start']}({end_time}) to {data['candles'][-1]['start']}")
        # How are we supposed to guess this: open, high, low, close, volume
        return [
            [
                self.ensure_timestamp_in_seconds(row['start']),
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                row['volume'],
                0, 0, 0, 0
            ] for row in data['candles']
        ]

    async def listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        if self.interval in CONSTANTS.WS_INTERVALS:
            await super().listen_for_subscriptions()
        else:
            self.logger().warning(f"Using REST loop for {self.interval} (not in {CONSTANTS.WS_INTERVALS})")
            while True:
                try:
                    await self._listen_to_fetch()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.logger().exception(
                        "Unexpected error occurred when fetching REST periodic public klines. Retrying in 1 seconds...",
                    )
                    await self._sleep(1.0)

    def _update_candles(
            self,
            candles: np.ndarray,
            call_history: bool = True,
            extend_left: bool = False
    ):
        """
        Updates the candles data with the new candles data.
        """
        if len(self._candles) == 0:
            if len(candles) > self._candles.maxlen:
                candles = candles[-self._candles.maxlen:]
            self._candles.extend(candles)
            if call_history:
                self._ws_candle_available.set()
                safe_ensure_future(self.fill_historical_candles())

        elif not extend_left:
            latest_timestamp = int(self._candles[-1][0])
            candles = candles[candles[:, 0] > latest_timestamp]
            if len(candles) > self._candles.maxlen - len(self._candles):
                candles = candles[-(self._candles.maxlen - len(self._candles)):]
            self._candles.extend(candles)
        else:
            earliest_timestamp = int(self._candles[0][0])
            candles = candles[candles[:, 0] < earliest_timestamp]
            self._candles.extendleft(candles)

    async def _listen_to_fetch(self):
        """
        Repeatedly calls fetch_candles on interval.
        """
        self.logger().debug("_listen_to_fetch() started...")
        candles: np.ndarray = await self.fetch_candles(end_time=int(time.time()))
        candles: np.ndarray = self.sanitize_data_to_interval(
            candles,
            interval_in_s=self.get_seconds_from_interval(self.interval),
            sort=True,
            from_start=False,
            logger=self.logger(),
        )

        self.logger().debug(f"_listen_to_fetch() Received {len(candles)} candles for {self.interval}:")

        self._update_candles(candles, call_history=True)
        # self._candles = self.sanitize_data_to_interval(
        #     self._candles,
        #     self.get_seconds_from_interval(self.interval),
        #     sort=True,
        #     from_start=False)

        while True:
            try:
                self.logger().debug(f"Fetching candles repeatedly on {self.interval}...")
                end_time: int = int(time.time())
                start_time = None
                if len(self._candles) > 0:
                    start_time = int(self._candles[0][0])

                candles = await self.fetch_candles(end_time=end_time, start_time=start_time)
                candles: np.ndarray = self.sanitize_data_to_interval(
                    candles,
                    interval_in_s=self.get_seconds_from_interval(self.interval),
                    sort=True,
                    from_start=False)

                self.logger().debug(f"   '-> Received {len(candles)} candles for {start_time}/{end_time} for {self.interval}:")
                self._update_candles(candles, call_history=False)
                await self._sleep(self.get_seconds_from_interval(self.interval))

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public REST candle call. Retrying in 1 "
                    "seconds...",
                )
                await self._sleep(1.0)

    def ws_subscription_payload(self):
        return {
            "type": "subscribe",
            "product_ids": [self._ex_trading_pair],
            "channel": "candles",
        }

    async def _process_websocket_messages_task(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data

            raw_candles = np.empty((0, 10))
            for parsed_message in self._parse_websocket_message(data):
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
                    raw_candles = np.append(raw_candles, [candles_row], axis=0)

            if len(raw_candles) == 0:
                continue

            raw_candles = self.sanitize_data_to_interval(
                raw_candles,
                interval_in_s=self.get_seconds_from_interval(self.interval),
                sort=True,
                from_start=False,
            )
            self._update_candles(raw_candles, call_history=True)

    def _parse_websocket_message(self, data: dict):
        self.logger().debug(f"Received websocket message: {data}")

        if data is None or "events" not in data or "channel" not in data or "candles" not in data["channel"]:
            self.logger().debug("No data:")
            return

        self.logger().debug(f"   events: {len(data['events'])}")
        for e in data["events"]:
            self.logger().debug(f"   candles: {len(e['candles'])}")
            for d in e["candles"]:
                candles_row_dict = {"timestamp": self.ensure_timestamp_in_seconds(d["start"])}
                candles_row_dict["open"] = d["open"]
                candles_row_dict["high"] = d["high"]
                candles_row_dict["low"] = d["low"]
                candles_row_dict["close"] = d["close"]
                candles_row_dict["volume"] = d["volume"]
                candles_row_dict["quote_asset_volume"] = 0
                candles_row_dict["n_trades"] = 0
                candles_row_dict["taker_buy_base_volume"] = 0
                candles_row_dict["taker_buy_quote_volume"] = 0

                yield candles_row_dict
