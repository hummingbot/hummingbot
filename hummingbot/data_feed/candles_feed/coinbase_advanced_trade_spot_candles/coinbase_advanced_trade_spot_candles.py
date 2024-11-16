import asyncio
import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

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
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.candle_data import CandleData
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.mixin_fetch_candle_data import (
    MixinFetchCandleData,
)
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.mixin_ws_operations import MixinWSOperations
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.utils import (
    sanitize_data,
    update_deque_from_sequence,
    yield_candle_data_from_dict,
)
from hummingbot.logger import HummingbotLogger


class CoinbaseAdvancedTradeSpotCandles(
    MixinFetchCandleData,
    MixinWSOperations,
    CandlesBase,
):
    """Class for managing Coinbase Advanced Trade candle data.

    Handles fetching and processing of candle data from Coinbase Advanced Trade,
    supporting both REST and WebSocket connections.

    :param trading_pair: The trading pair to track (e.g. "BTC-USD")
    :param interval: Candle interval (e.g. "1m", "5m")
    :param max_records: Maximum number of candles to store
    """
    _logger: Optional[HummingbotLogger] = None
    web_utils = web_utils

    def __init__(
            self,
            trading_pair: str,
            interval: str = "1m",
            max_records: int = 150,
    ):
        super().__init__(trading_pair, interval, max_records)
        self._api_factory = WebAssistantsFactory(throttler=CoinbaseExchangeThrottler)

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        """Get the logger for this class.

        :returns: Logger instance
        :rtype: HummingbotLogger
        """
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(__name__)
        return cls._logger

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
    def candles_deque(self) -> deque:
        """Candles deque for the exchange."""
        return super()._candles

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

    def _get_rest_candles_params(
            self,
            start_time: int | None = None,
            end_time: int | None = None,
            limit: int | None = None,
    ) -> dict[str, Any]:
        params = {
            "granularity": CONSTANTS.INTERVALS[self.interval],
            "start": self.ensure_timestamp_in_seconds(start_time) if start_time else None,
        }
        if end_time:
            params["end"] = self.ensure_timestamp_in_seconds(end_time)
        self.logger().debug(f"REST candles params: {params}")
        return params

    async def listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        if self.interval in CONSTANTS.WS_INTERVALS:
            await self._catsc_listen_for_subscriptions()
        else:
            await self._catsc_listen_to_fetch()

    def __ws_subscription_payload(self):
        return {
            "type": "subscribe",
            "product_ids": [self._ex_trading_pair],
            "channel": "candles",
        }

    async def __catsc_listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._catsc_process_websocket_messages(websocket_assistant=ws)
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

    async def _catsc_listen_to_fetch(self):
        """
        Repeatedly calls fetch_candles on interval.
        """
        self.logger().debug("_listen_to_fetch() started...")
        candles: tuple[CandleData, ...] = await self._fetch_candles(end_time=int(time.time()))
        await self._initialize_deque_from_sequence(candles)

        while True:
            try:
                start_time: int = int(self._candles[-1][0]) if len(self._candles) > 0 else None
                end_time: int = int(datetime.now().timestamp())
                candles = await self._fetch_candles(end_time=end_time, start_time=start_time)
                await self._initialize_deque_from_sequence(candles)
                await self._sleep(self.get_seconds_from_interval(self.interval))

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public REST candle call. Retrying in 1 "
                    "seconds...",
                )
                await self._sleep(1.0)

    async def __catsc_process_websocket_messages(self, websocket_assistant: WSAssistant):
        def _parse_websocket_message(_data: dict[str, Any]) -> Generator[CandleData, Any, None]:
            self.logger().debug(f"Received websocket message: {data}")
            if _data is not None and "events" in _data:
                for e in _data["events"]:
                    if "candles" in e:
                        yield from yield_candle_data_from_dict(e)

        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data

            if isinstance(data, WSJSONRequest):
                await websocket_assistant.send(request=data)
                continue

            raw_candles: tuple[CandleData, ...] = ()
            for candle in _parse_websocket_message(data):
                raw_candles += (candle,)

            if not raw_candles:
                continue

            raw_candles = sanitize_data(
                raw_candles,
                interval_in_s=self.get_seconds_from_interval(self.interval),
            )
            await self._initialize_deque_from_sequence(raw_candles)

    async def _catsc_fill_historical_candles(self):
        """
        This method fills the historical candles in the _candles deque until it reaches the maximum length.
        """
        while not self.ready:
            await self._ws_candle_available.wait()
            try:
                end_time = self._candles[0][0]
                missing_records = self._candles.maxlen - len(self._candles)
                candles: tuple[CandleData, ...] = await self._fetch_candles(end_time=end_time, limit=missing_records)
                update_deque_from_sequence(self._candles, candles, extend_left=True)
            except asyncio.CancelledError:
                raise
            except ValueError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when getting historical klines. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)

    async def fill_historical_candles(self):
        return NotImplementedError

    async def _process_websocket_messages_task(self, websocket_assistant: WSAssistant):
        return NotImplementedError

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None):
        return NotImplementedError
