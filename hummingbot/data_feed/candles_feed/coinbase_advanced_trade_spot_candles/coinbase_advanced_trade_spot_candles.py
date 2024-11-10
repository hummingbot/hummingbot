import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils as web_utils
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants import (
    DEFAULT_DOMAIN,
    REST_URL,
    SERVER_TIME_EP,
    WSS_URL,
)
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
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
        # if CoinbaseAdvancedTradeExchange.class_throttler is not None:
        #     self.logger().debug(f"Initializing {self.name} {interval} candles feed with class throttler")
        #     self._api_factory = WebAssistantsFactory(throttler=CoinbaseAdvancedTradeExchange.class_throttler)
        # else:
        #     self.logger().debug(f"Initializing {self.name} {interval} candles feed with no throttler")
        #     self._api_factory = WebAssistantsFactory()

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
        self.logger().debug(f"Getting rate limits for {CONSTANTS.RATE_LIMITS}")
        return CONSTANTS.RATE_LIMITS

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
    def _is_last_candle_not_included_in_rest_request(self):
        return False

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
        self.logger().debug(f"Received {data} candles for {end_time} for {self.interval}:")
        # How are we supposed to guess this: open, high, low, close, volume
        return [
            [self.ensure_timestamp_in_seconds(row['start']), row['open'], row['high'], row['low'], row['close'], row['volume'],
             0, 0, 0, 0]
            for row in data['candles']
        ]

    async def listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        self.logger().debug("Listening for subscriptions...")
        await self._listen_to_fetch()

    async def _listen_to_fetch(self):
        """
        Repeatedly calls fetch_candles on interval.
        """
        while True:
            try:
                self.logger().debug("_listen_to_fetch() called...")
                end_time: int = int(time.time())

                start_time = None
                if len(self._candles) > 0:
                    start_time = int(self._candles[0][0])

                candles = await self.fetch_candles(end_time=end_time, start_time=start_time)

                self.logger().debug(f"Received {len(candles)} candles for {start_time}/{end_time} for {self.interval}:")
                # self.logger().debug(f"\t[{int(candles[0][0])} ... {int(candles[-1][0])}] -> [{int(self._candles[0][0])}]")

                self._candles.extendleft(candles)
                await self._sleep(self.get_seconds_from_interval(self.interval))
                self.logger().debug(f"Waited {self.get_seconds_from_interval(self.interval)} s")

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

    def _parse_websocket_message(self, data: dict):
        if data is None or "events" not in data or "candles" not in data["events"]:
            return

        d: dict = data["events"]["candles"]
        candles_row_dict = {"timestamp": self.ensure_timestamp_in_seconds(d["start"])}
        candles_row_dict["open"] = d["open"]
        candles_row_dict["high"] = d["high"]
        candles_row_dict["low"] = d["low"]
        candles_row_dict["close"] = d["close"]
        candles_row_dict["volume"] = d["volume"]
        return candles_row_dict
